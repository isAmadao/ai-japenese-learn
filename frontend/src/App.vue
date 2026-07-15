<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView, RouterLink, useRouter } from 'vue-router'
import { fetchDictionaryStatus, streamUpgradeDictionary, rollbackDictionary } from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const dictStatus = ref<string>('pykakasi')
const dictDesc = ref<string>('')
const showDictModal = ref(false)
const upgrading = ref(false)
const upgradeProgress = ref<string[]>([])
const upgradeResult = ref<string | null>(null)
const upgradeSuccess = ref(false)

onMounted(async () => {
  try {
    const s = await fetchDictionaryStatus()
    dictStatus.value = s.current
    dictDesc.value = s.description
  } catch { /* silent */ }
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}

function handleUpgrade() {
  upgrading.value = true
  upgradeResult.value = null
  upgradeSuccess.value = false
  upgradeProgress.value = []

  streamUpgradeDictionary(
    (text) => {
      upgradeProgress.value = [...upgradeProgress.value, text]
    },
    (message) => {
      upgradeResult.value = message
      upgradeSuccess.value = true
      dictStatus.value = 'mecab'
      dictDesc.value = '已升级至 MeCab（完整日语词典，生僻汉字也可准确注音）'
      upgrading.value = false
    },
    (message) => {
      upgradeResult.value = message
      upgradeSuccess.value = false
      upgrading.value = false
    },
  )
}

async function handleRollback() {
  upgrading.value = true
  upgradeResult.value = null
  upgradeProgress.value = ['正在回退...']
  try {
    const r = await rollbackDictionary()
    upgradeResult.value = r.message
    upgradeSuccess.value = r.success
    if (r.success) {
      dictStatus.value = 'pykakasi'
      dictDesc.value = '当前使用 pykakasi（轻量词典，覆盖常用汉字读音）'
    }
  } catch (e: any) {
    console.error('Rollback error:', e)
    upgradeResult.value = e?.response?.data?.detail || e?.message || '回退失败，请重试'
    upgradeSuccess.value = false
  } finally {
    upgrading.value = false
  }
}
</script>

<template>
  <nav>
    <!-- Decorative nail holes -->
    <span class="nav-nail" style="left:8px"></span>
    <span class="nav-nail" style="right:8px"></span>

    <RouterLink to="/" class="logo">🌾 日本語学習</RouterLink>
    <RouterLink to="/">🏠 首页</RouterLink>
    <RouterLink to="/search">🔍 搜索</RouterLink>
    <RouterLink to="/favorites">⭐ 收藏</RouterLink>
    <RouterLink to="/learned">✅ 已学习</RouterLink>
    <RouterLink to="/mastered">🎯 已熟练</RouterLink>
    <RouterLink to="/settings" class="nav-settings">⚙️ 设置</RouterLink>
    <RouterLink v-if="auth.isAdmin" to="/admin" class="nav-admin">🔧 管理</RouterLink>

    <div class="nav-right">
      <template v-if="auth.isAuthenticated">
        <span class="nav-user">👤 {{ auth.user?.username }}</span>
        <button class="nav-logout" @click="handleLogout">登出</button>
      </template>
      <template v-else>
        <RouterLink to="/login" class="nav-login">登录</RouterLink>
      </template>
      <button class="dict-btn" :class="{ mecab: dictStatus === 'mecab' }" @click="showDictModal = true" :title="dictDesc">
        <template v-if="dictStatus === 'mecab'">📗 MeCab</template>
        <template v-else>📘 词典</template>
      </button>
    </div>
  </nav>

  <!-- Dictionary upgrade modal -->
  <Teleport to="body">
    <div v-if="showDictModal" class="modal-overlay" @click.self="showDictModal = false">
      <div class="modal">
        <h2>📖 词典设置</h2>
        <p class="dict-current">
          当前：<strong>{{ dictStatus === 'mecab' ? 'MeCab（完整版）' : 'pykakasi（轻量版）' }}</strong>
        </p>
        <p class="dict-desc">{{ dictDesc }}</p>

        <div v-if="dictStatus !== 'mecab'" class="dict-upgrade-section">
          <div class="dict-compare">
            <div class="dict-compare-item">
              <div class="dict-compare-label">当前（pykakasi）</div>
              <ul>
                <li>✅ 覆盖 JLPT N5-N1 常用汉字</li>
                <li>⚡ 轻量，~10MB</li>
                <li>✅ 开机即用，无需额外安装</li>
              </ul>
            </div>
            <div class="dict-compare-item">
              <div class="dict-compare-label">升级后（MeCab）</div>
              <ul>
                <li>✅ 覆盖所有汉字（含生僻字）</li>
                <li>📦 额外 ~50MB</li>
                <li>⚠️ 需在线安装，约 1-2 分钟</li>
              </ul>
            </div>
          </div>

          <!-- Progress bar during upgrade -->
          <div v-if="upgrading" class="dict-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: upgradeProgress.length > 5 ? '90%' : '30%' }"></div>
            </div>
            <div class="progress-log">
              <div v-for="(line, i) in upgradeProgress.slice(-3)" :key="i" class="progress-line">{{ line }}</div>
              <div v-if="upgradeProgress.length === 0" class="progress-line dim">准备中...</div>
            </div>
          </div>

          <div v-if="!upgrading && !upgradeResult" class="dict-actions">
            <button class="btn btn-primary" @click="handleUpgrade">
              📗 升级至 MeCab 词典
            </button>
          </div>
        </div>

        <div v-else class="dict-ok">
          <div class="dict-ok-text">✅ 已使用完整 MeCab 词典</div>
          <div class="dict-ok-sub">完整词典可准确校验生僻汉字读音</div>

          <div v-if="upgrading" class="dict-progress" style="margin-top:12px">
            <div class="progress-bar">
              <div class="progress-fill" style="width:60%"></div>
            </div>
            <div class="progress-log">
              <div class="progress-line">正在回退至 pykakasi...</div>
            </div>
          </div>

          <button v-if="!upgrading" class="btn btn-outline btn-sm" style="margin-top: 12px" @click="handleRollback">
            回退至 pykakasi 轻量版
          </button>
        </div>

        <div v-if="upgradeResult" class="dict-result" :class="{ success: upgradeSuccess }">
          {{ upgradeResult }}
          <button v-if="upgradeSuccess" class="btn btn-outline btn-sm" style="margin-top:8px" @click="showDictModal = false">知道了</button>
        </div>

        <div class="modal-actions">
          <button class="btn btn-outline" @click="showDictModal = false">关闭</button>
        </div>
      </div>
    </div>
  </Teleport>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.nav-right {
  margin-left: auto;
  display: flex;
  align-items: center;
}

.nav-nail {
  position: absolute;
  top: 6px;
  width: 10px;
  height: 10px;
  background: var(--warm-brown-dark);
  border-radius: 50%;
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.15);
}

.nav-user {
  font-size: 0.75rem;
  color: var(--text-light);
  margin-right: 8px;
  white-space: nowrap;
}
.nav-login, .nav-logout {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.55rem;
  padding: 6px 12px;
  margin-right: 8px;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  transition: all 0.05s step-start;
  text-decoration: none;
}
.nav-login:hover, .nav-logout:hover {
  background: var(--golden-light);
  border-color: var(--golden);
}

.dict-btn {
  padding: 8px 16px;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.6rem;
  border: 3px solid var(--wood-dark);
  background: var(--cream);
  color: var(--warm-brown);
  cursor: pointer;
  transition: all 0.05s step-start;
  font-weight: 400;
  letter-spacing: 1px;
  box-shadow: 2px 2px 0 var(--wood-dark);
}

.dict-btn:hover {
  background: var(--wood-light);
  transform: translate(-1px, -1px);
}

.dict-btn.mecab {
  border-color: var(--grass-dark);
  color: var(--grass-dark);
}
.dict-btn.mecab:hover {
  background: var(--grass-light);
}

/* ===== Modal Inner Styles ===== */
.dict-current { font-size: 0.9rem; margin-bottom: 4px; color: var(--cream); }
.dict-desc { color: var(--wood-light); font-size: 0.8rem; margin-bottom: 16px; }

.dict-compare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}
.dict-compare-item {
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  padding: 12px;
  box-shadow: inset -2px -2px 0 rgba(0,0,0,0.05);
}
.dict-compare-label {
  font-weight: 700;
  font-size: 0.8rem;
  margin-bottom: 8px;
  color: var(--text);
  font-family: 'Press Start 2P', monospace;
  letter-spacing: 1px;
}
.dict-compare-item ul {
  list-style: none;
  padding: 0;
  font-size: 0.8rem;
}
.dict-compare-item li {
  margin-bottom: 4px;
  color: var(--text-light);
}

.dict-actions { text-align: center; margin: 16px 0; }
.dict-result {
  text-align: center;
  padding: 12px;
  margin: 12px 0;
  border: 3px solid var(--warning);
  background: var(--bg-hint);
  color: var(--warm-brown-dark);
  font-size: 0.85rem;
}
.dict-result.success {
  border-color: var(--success);
  background: #E8F8E0;
  color: #3A7A2A;
}

.dict-ok {
  text-align: center;
  padding: 16px;
}
.dict-ok-text {
  color: var(--success);
  font-size: 0.95rem;
  font-weight: 700;
}
.dict-ok-sub {
  color: var(--text-light);
  font-size: 0.8rem;
  margin-top: 4px;
}

.dict-progress { margin: 16px 0; }
.progress-bar {
  width: 100%;
  height: 10px;
  background: var(--cream);
  border: 3px solid var(--wood-dark);
  overflow: hidden;
  margin-bottom: 10px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--grass), var(--golden));
  transition: width 0.5s ease;
  animation: progress-pulse 1.5s infinite;
}
@keyframes progress-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.progress-log {
  background: #2A2018;
  border: 3px solid var(--wood-dark);
  padding: 10px;
  max-height: 120px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 0.75rem;
}
.progress-line { color: #D0C0A0; line-height: 1.4; word-break: break-all; }
.progress-line.dim { color: #6A5A4A; }

/* Admin nav link — gold accent */
nav a.nav-admin {
  border-color: var(--golden) !important;
  color: var(--golden-light) !important;
}
nav a.nav-admin:hover {
  background: var(--golden) !important;
  color: var(--text) !important;
  border-color: var(--golden) !important;
}
</style>
