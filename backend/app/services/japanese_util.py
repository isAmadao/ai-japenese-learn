"""Japanese language utilities — kana verification.

Default: pykakasi (lightweight, ~10MB).
Optional upgrade: fugashi + unidic-lite for full MeCab accuracy (~50MB extra).

Usage:
    verify_kana("食べる", "たべる") → "たべる"  (correct via either engine)
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── User preference file (persists across restarts) ─────────
# The user can choose to skip MeCab even if the packages are installed.
_DICT_PREFERENCE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / ".dict_preference"


def _get_dict_preference() -> str:
    """Read the persisted dictionary preference. Returns 'pykakasi' or 'mecab'."""
    try:
        if _DICT_PREFERENCE_FILE.exists():
            val = _DICT_PREFERENCE_FILE.read_text().strip()
            return val if val in ("pykakasi", "mecab") else "mecab"
    except Exception:
        pass
    return "mecab"  # default: try MeCab if available


def _set_dict_preference(pref: str):
    """Persist the user's dictionary preference."""
    try:
        _DICT_PREFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DICT_PREFERENCE_FILE.write_text(pref)
        logger.info(f"Dictionary preference saved: {pref}")
    except Exception as e:
        logger.warning(f"Failed to save dictionary preference: {e}")

# ── pykakasi (default, always available) ────────────────────

_pykakasi = None


def _get_pykakasi():
    global _pykakasi
    if _pykakasi is None:
        try:
            import pykakasi
            _pykakasi = pykakasi.Kakasi()
            logger.info("pykakasi loaded (~10MB)")
        except ImportError:
            logger.warning("pykakasi not installed")
    return _pykakasi


def _pykakasi_kana(word: str) -> Optional[str]:
    """Convert kanji to hiragana via pykakasi."""
    kks = _get_pykakasi()
    if kks is None:
        return None
    try:
        result = kks.convert(word)
        return "".join(item["hira"] for item in result)
    except Exception as e:
        logger.debug(f"pykakasi failed for '{word}': {e}")
        return None


# ── MeCab (optional, upgradable) ────────────────────────────

_mecab_tagger = None


def _try_load_mecab() -> bool:
    """Try to load fugashi + unidic-lite.  Returns True if available.

    If the user previously chose pykakasi (preference file), skips MeCab
    even if the packages are installed.
    """
    global _mecab_tagger

    if _get_dict_preference() == "pykakasi":
        logger.info("Skipping MeCab (user preference: pykakasi)")
        _mecab_tagger = None
        return False

    try:
        from fugashi import Tagger
        _mecab_tagger = Tagger("-Owakati")
        logger.info("MeCab tagger loaded (upgraded dictionary)")
        return True
    except Exception:
        _mecab_tagger = None
        return False


def _mecab_kana(word: str) -> Optional[str]:
    """Extract hiragana reading via MeCab."""
    if _mecab_tagger is None:
        return None
    try:
        for node in _mecab_tagger(word):
            feat = node.feature
            kana = None
            if hasattr(feat, "kana") and feat.kana and feat.kana != "*":
                kana = feat.kana
            elif hasattr(feat, "lForm") and feat.lForm and feat.lForm != "*":
                kana = feat.lForm
            elif isinstance(feat, str):
                parts = feat.split(",")
                if len(parts) >= 10 and parts[9] and parts[9] != "*":
                    kana = parts[9]
                elif len(parts) >= 8 and parts[7] and parts[7] != "*":
                    kana = parts[7]
            if kana:
                # MeCab returns katakana → convert to hiragana
                return "".join(
                    chr(ord(c) - 96) if "ァ" <= c <= "ヴ" else c
                    for c in kana
                )
    except Exception as e:
        logger.debug(f"MeCab lookup failed for '{word}': {e}")
    return None


# ── Public API ──────────────────────────────────────────────

def verify_kana(word: str, llm_kana: str) -> str:
    """Verify / correct kana reading.

    Uses pykakasi by default; if MeCab (fugashi) is installed, prefers it
    for better accuracy on rare kanji.
    """
    if not word or not llm_kana:
        return llm_kana

    # Try MeCab first if available (higher accuracy)
    if _mecab_tagger is not None:
        mecab_result = _mecab_kana(word)
        if mecab_result:
            return mecab_result

    # Fall back to pykakasi
    pykakasi_result = _pykakasi_kana(word)
    if pykakasi_result:
        # Compare with LLM output — if they disagree, trust pykakasi
        return pykakasi_result

    return llm_kana


def batch_verify_kana(words: list[dict]) -> list[dict]:
    """Verify kana for all words in a batch. Modifies dicts in-place."""
    changed = 0
    for w in words:
        name = w.get("name", "")
        kana = w.get("kana", "")
        if name and kana:
            corrected = verify_kana(name, kana)
            if corrected and corrected != kana:
                logger.info(f"Kana corrected: {name} {kana} → {corrected}")
                w["kana"] = corrected
                changed += 1
    if changed:
        logger.info(f"Corrected {changed}/{len(words)} kana readings")
    return words


# ── In-app upgrade — streaming ──────────────────────────────

MECAB_PACKAGES = ["fugashi", "unidic-lite"]


def is_mecab_available() -> bool:
    """Check if MeCab (fugashi + unidic-lite) is already installed."""
    if _mecab_tagger is not None:
        return True
    return _try_load_mecab()


def upgrade_to_mecab_stream():
    """Stream pip install progress line by line (for SSE).

    Yields dicts:
      {"type":"progress","text":"..."}  — pip output
      {"type":"done","message":"..."}   — success
      {"type":"error","message":"..."}  — failure

    Handles Windows Defender INSTALLER.tmp lock by retrying with manual
    file copy as a fallback.
    """
    if is_mecab_available():
        yield {"type": "done", "message": "MeCab 词典已安装，无需重复升级"}
        return

    yield {"type": "progress", "text": "正在下载 fugashi + unidic-lite..."}

    def _fix_installer_tmp():
        """Post-install fix: copy trapped INSTALLER.tmp → INSTALLER.

        Windows Defender may lock .tmp files during pip's record-keeping,
        preventing the rename to 'INSTALLER'.  Manually copy the content
        so the package is recognized as installed.
        """
        candidates = set()
        try:
            import site as _site
            candidates.add(_site.getusersitepackages())
        except Exception:
            pass
        try:
            from distutils.sysconfig import get_python_lib
            candidates.add(get_python_lib())
        except Exception:
            pass
        # Also scan sys.path for any site-packages
        candidates.update(
            p for p in sys.path if "site-packages" in p and os.path.isdir(p)
        )

        fixed = False
        for pkg in ("fugashi", "unidic_lite"):
            for sp in candidates:
                if not sp or not os.path.isdir(sp):
                    continue
                pkg_dir = os.path.join(sp, pkg)
                tmp_file = os.path.join(pkg_dir, "INSTALLER.tmp")
                installer = os.path.join(pkg_dir, "INSTALLER")
                if os.path.exists(tmp_file) and not os.path.exists(installer):
                    try:
                        import shutil
                        shutil.copy2(tmp_file, installer)
                        logger.info(f"Fixed INSTALLER.tmp → INSTALLER for {pkg} in {sp}")
                        fixed = True
                        break
                    except OSError as e:
                        logger.debug(f"Could not fix INSTALLER for {pkg}: {e}")
        return fixed

    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", *MECAB_PACKAGES],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
        # Stream pip output
        for line in iter(process.stdout.readline, ""):
            stripped = line.strip()
            if stripped:
                yield {"type": "progress", "text": stripped}

        process.wait(timeout=120)

        if process.returncode == 0:
            _try_load_mecab()
            if _mecab_tagger is not None:
                _set_dict_preference("mecab")
                yield {"type": "done", "message": "MeCab 词典升级成功，生僻汉字读音校验已启用"}
            else:
                yield {"type": "error", "message": "安装完成但加载失败，请重试"}
        else:
            # ── Retry: possibly Windows Defender locked INSTALLER.tmp ──
            logger.info("pip install failed — trying INSTALLER.tmp workaround...")
            yield {"type": "progress", "text": "检查 Windows Defender 文件锁..."}
            if _fix_installer_tmp():
                yield {"type": "progress", "text": "文件锁已修复，尝试加载 MeCab..."}
                _try_load_mecab()
                if _mecab_tagger is not None:
                    _set_dict_preference("mecab")
                    yield {"type": "done",
                           "message": "MeCab 词典安装成功（已绕过 Windows Defender 文件锁）"}
                    return
            yield {"type": "error",
                   "message": f"安装失败，退出码 {process.returncode}。"
                              f"请尝试以管理员身份运行: python scripts/fix-pip-lock.py --defender"}

    except subprocess.TimeoutExpired:
        process.kill()
        yield {"type": "error", "message": "安装超时，请检查网络连接"}
    except Exception as e:
        yield {"type": "error", "message": f"安装异常: {str(e)}"}


def uninstall_mecab() -> dict:
    """Uninstall fugashi + unidic-lite, fall back to pykakasi.

    Even if pip uninstall fails (e.g. file locked on Windows), we force
    the tagger to None so pykakasi takes over immediately.
    """
    global _mecab_tagger
    _mecab_tagger = None  # force fallback to pykakasi immediately
    _set_dict_preference("pykakasi")  # persist so restart keeps pykakasi

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", *MECAB_PACKAGES],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return {"success": True, "message": "已回退至 pykakasi 轻量词典"}
        # Non-zero exit — fall through to warning below
        logger.warning(f"pip uninstall exited {result.returncode}: {result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"pip uninstall exception (non-fatal): {e}")

    # Even if pip failed, tagger is None → verify_kana uses pykakasi now
    return {"success": True, "message": "已切换至 pykakasi（包文件需重启后清理）"}
