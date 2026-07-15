<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { updateProfile, changePassword } from '@/api'

const auth = useAuthStore()

// ── Profile ──────────────────────────────────────────────────
const nickname = ref(auth.user?.username || '')
const profileMsg = ref('')
const profileError = ref('')
const profileSaving = ref(false)

async function saveProfile() {
  if (!nickname.value.trim() || nickname.value.trim().length < 2) {
    profileError.value = '昵称至少 2 个字符'
    return
  }
  profileSaving.value = true
  profileError.value = ''
  profileMsg.value = ''
  try {
    const result = await updateProfile(nickname.value.trim())
    // Update store
    if (auth.user) {
      auth.user.username = result.username
      localStorage.setItem('ai_jp_user', JSON.stringify(auth.user))
    }
    profileMsg.value = '昵称已更新'
  } catch (e: any) {
    profileError.value = e?.response?.data?.detail || '更新失败'
  } finally {
    profileSaving.value = false
  }
}

// ── Password ─────────────────────────────────────────────────
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const showCurrentPw = ref(false)
const showNewPw = ref(false)
const showConfirmPw = ref(false)
const passMsg = ref('')
const passError = ref('')
const passSaving = ref(false)

const passwordStrength = computed(() => {
  const pw = newPassword.value
  if (!pw) return { level: 0, label: '', color: '', width: '0%' }
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  if (score <= 1) return { level: 1, label: '弱', color: 'var(--danger)', width: '25%' }
  if (score <= 2) return { level: 2, label: '中', color: '#e6a817', width: '50%' }
  if (score <= 3) return { level: 3, label: '强', color: 'var(--grass-dark)', width: '75%' }
  return { level: 4, label: '非常强', color: '#2e7d32', width: '100%' }
})

async function savePassword() {
  if (!currentPassword.value) {
    passError.value = '请输入当前密码'
    return
  }
  if (!newPassword.value || newPassword.value.length < 4) {
    passError.value = '新密码至少 4 个字符'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    passError.value = '两次密码输入不一致'
    return
  }
  passSaving.value = true
  passError.value = ''
  passMsg.value = ''
  try {
    const result = await changePassword(currentPassword.value, newPassword.value)
    passMsg.value = result.message || '密码已更新'
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e: any) {
    passError.value = e?.response?.data?.detail || '修改失败'
  } finally {
    passSaving.value = false
  }
}
</script>

<template>
  <div class="settings-page">
    <h1 class="page-title">⚙️ 个人设置</h1>

    <!-- ── Profile ───────────────────── -->
    <div class="card settings-card">
      <div class="card-stripe"></div>
      <h2 class="section-title">基本资料</h2>

      <div class="info-row">
        <span class="info-label">账号</span>
        <span class="info-value account-code">U{{ String(auth.user?.id || '').padStart(5, '0') }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">邮箱</span>
        <span class="info-value">{{ auth.user?.email || '-' }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">账号状态</span>
        <span class="info-value">
          <span v-if="auth.user?.is_verified" class="badge-verified">已验证</span>
          <span v-else class="badge-unverified">未验证</span>
        </span>
      </div>

      <div class="field">
        <label for="settings-nickname">昵称</label>
        <input id="settings-nickname" v-model="nickname" type="text"
          placeholder="输入新昵称" maxlength="50" />
      </div>

      <p v-if="profileMsg" class="msg-success">{{ profileMsg }}</p>
      <p v-if="profileError" class="msg-error">⚠ {{ profileError }}</p>

      <button class="btn btn-primary" :disabled="profileSaving" @click="saveProfile">
        {{ profileSaving ? '保存中...' : '保存昵称' }}
      </button>
    </div>

    <!-- ── Password ──────────────────── -->
    <div class="card settings-card">
      <div class="card-stripe"></div>
      <h2 class="section-title">修改密码</h2>

      <div class="field">
        <label for="settings-current-pass">当前密码</label>
        <div class="pw-field">
          <input id="settings-current-pass" v-model="currentPassword"
            :type="showCurrentPw ? 'text' : 'password'"
            placeholder="输入当前密码" autocomplete="current-password" />
          <button type="button" class="pw-toggle" @click="showCurrentPw = !showCurrentPw" tabindex="-1">
            {{ showCurrentPw ? '🙈' : '👁️' }}
          </button>
        </div>
      </div>
      <div class="field">
        <label for="settings-new-pass">新密码</label>
        <div class="pw-field">
          <input id="settings-new-pass" v-model="newPassword"
            :type="showNewPw ? 'text' : 'password'"
            placeholder="输入新密码（至少 4 位）" autocomplete="new-password" />
          <button type="button" class="pw-toggle" @click="showNewPw = !showNewPw" tabindex="-1">
            {{ showNewPw ? '🙈' : '👁️' }}
          </button>
        </div>
        <div v-if="newPassword" class="strength-bar-wrap">
          <div class="strength-bar" :style="{ width: passwordStrength.width, backgroundColor: passwordStrength.color }"></div>
        </div>
        <div v-if="newPassword" class="strength-label" :style="{ color: passwordStrength.color }">
          强度：{{ passwordStrength.label }}
        </div>
      </div>
      <div class="field">
        <label for="settings-confirm-pass">确认新密码</label>
        <div class="pw-field">
          <input id="settings-confirm-pass" v-model="confirmPassword"
            :type="showConfirmPw ? 'text' : 'password'"
            placeholder="再次输入新密码" autocomplete="new-password" />
          <button type="button" class="pw-toggle" @click="showConfirmPw = !showConfirmPw" tabindex="-1">
            {{ showConfirmPw ? '🙈' : '👁️' }}
          </button>
        </div>
      </div>

      <p v-if="passMsg" class="msg-success">{{ passMsg }}</p>
      <p v-if="passError" class="msg-error">⚠ {{ passError }}</p>

      <button class="btn btn-primary" :disabled="passSaving" @click="savePassword">
        {{ passSaving ? '修改中...' : '修改密码' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 500px;
  margin: 0 auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.page-title {
  font-family: 'Press Start 2P', monospace;
  font-size: clamp(0.55rem, 2vw, 0.75rem);
  color: var(--cream);
  text-shadow: 2px 2px 0 var(--warm-brown-dark);
  letter-spacing: 2px;
  margin: 0;
}
.settings-card {
  padding: 24px 20px;
  position: relative;
  overflow: hidden;
}
.card-stripe {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--golden), var(--grass-light), var(--pink), var(--golden));
}
.section-title {
  font-size: 0.95rem;
  color: var(--text);
  margin: 0 0 16px 0;
}
.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 2px solid var(--wood-light);
  margin-bottom: 12px;
}
.info-label {
  color: var(--text-light);
  font-size: 0.85rem;
}
.info-value {
  color: var(--text);
  font-size: 0.85rem;
}
.badge-verified {
  color: var(--grass-dark);
  font-weight: 600;
}
.badge-unverified {
  color: var(--text-muted);
}
.account-code {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.65rem;
  color: var(--golden);
  letter-spacing: 1px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.field label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text);
}
.field input {
  font-family: inherit;
  font-size: 0.9rem;
  padding: 10px 12px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
}
.field input:focus {
  border-color: var(--golden);
}
.pw-field {
  display: flex;
  align-items: center;
  border: 3px solid var(--wood-light);
  background: var(--cream);
}
.pw-field input {
  flex: 1;
  border: none !important;
  padding-right: 4px;
}
.pw-field:focus-within {
  border-color: var(--golden);
}
.pw-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px 10px;
  font-size: 1rem;
  line-height: 1;
}
.strength-bar-wrap {
  height: 4px;
  background: var(--wood-light);
  border-radius: 2px;
  overflow: hidden;
}
.strength-bar {
  height: 100%;
  transition: all 0.2s ease;
  border-radius: 2px;
}
.strength-label {
  font-size: 0.7rem;
  text-align: right;
  margin-top: -4px;
}
.btn {
  margin-top: 4px;
}
.msg-success {
  color: var(--grass-dark);
  font-size: 0.85rem;
  text-align: center;
  padding: 6px;
  background: rgba(74, 124, 89, 0.08);
  border: 2px solid var(--grass-dark);
}
.msg-error {
  color: var(--danger);
  font-size: 0.85rem;
  text-align: center;
  padding: 6px;
  background: rgba(208, 80, 80, 0.08);
  border: 2px solid var(--danger);
}
</style>
