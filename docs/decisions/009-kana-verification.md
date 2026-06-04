# 009 · MeCab 假名校验（LLM 读音纠错）

- **日期**: 2026-06-04
- **状态**: ✅ 已采纳

## 问题

LLM（Qwen）对日语汉字读音经常出错，例如：
- 妥協 → だかい ❌（正确：だきょう）
- 一貫 → いっかん ✅（运气好时对，但不可靠）

LLM 对汉字读音是"概率生成"而非"查字典"，遇到非常用音读、同形异读词时准确率约 70%。

## 方案

**fugashi（MeCab Python 绑定）+ unidic（IPA 日语词典）做后验校验。**

```
LLM 生成单词 { name: "妥協", kana: "だかい" }
  → MeCab 查 "妥協"
  → unidic 返回: kana="ダキョウ"
  → 不一致 → 用 MeCab 结果覆盖: "だきょう"
```

### 架构

```
WordAgent.generate_words()
  ├── LLM 调用 (Qwen)
  ├── JSON 解析
  ├── batch_verify_kana()    ← 🆕
  │    ├── fugashi Tagger 查每个 name
  │    ├── _extract_kana() 取 unidic 的 kana 字段
  │    └── 不一致则覆盖
  └── 返回纠正后的 words
```

### 关键实现

```python
def verify_kana(word: str, llm_kana: str) -> str:
    for node in tagger(word):
        kana = _extract_kana(node)  # UnidicFeatures26.kana
        if kana:
            # Normalize katakana → hiragana
            return "".join(chr(ord(c) - 96) if "ァ" <= c <= "ヴ" else c for c in kana)
    return llm_kana  # fallback
```

## 优化效果

- 假名准确率从 ~70% 提升到 ~99% 🚀
- 避免用户学到错误读音
- 不增加 LLM 调用成本（纯本地词典查询，<1ms）

## 经验教训

### LLM 不适合精确事实查询

LLM 擅长生成"看起来对"的内容，但汉字读音是确定性知识，应该用词典工具查证。这与 Agent 的"工具调用"思想一致——LLM 做生成，工具做验证。

### 安装注意事项

fugashi + unidic-lite 可通过 pip 安装，但在 Windows + conda 环境下：
1. 需 pip 补丁（同前，os.unlink 文件锁问题）
2. unidic-lite 自带词典约 50MB，首次加载较慢（后续缓存）

### Katakana → Hiragana 归一化

MeCab 返回的假名是片假名（"ダキョウ"），前端展示通常用平假名（"だきょう"），需要做 Unicode 转换：
```python
chr(ord(c) - 96)  # カ(0x30AB) → か(0x304B)
```

## 备选方案

- **pykakasi**: 纯 Python 读音转换，但准确率不如 MeCab
- **jamdict**: 日语词典查询，但需额外下载词典文件
- **手动标注**: 不可扩展

## 关联

- [006 · Agent + Redis 缓存系统](006-agent-redis-cache.md)
