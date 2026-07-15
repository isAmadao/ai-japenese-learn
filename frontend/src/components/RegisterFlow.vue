<script setup lang="ts">
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  fetchCaptcha,
  verifyCaptcha,
  sendVerificationCode,
  verifyEmailCode,
  resendVerificationCode,
  checkNicknameAvailable,
} from '@/api'
import type { CaptchaChallenge } from '@/types'

const router = useRouter()
const auth = useAuthStore()

// ── Steps: form → captcha → code → success ──────────────────
type Step = 'form' | 'captcha' | 'code' | 'success'
const step = ref<Step>('form')

// ── Form state ───────────────────────────────────────────────
const nickname = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPw = ref(false)
const showConfirm = ref(false)
const formErrors = reactive({ nickname: '', email: '', password: '', confirm: '' })
const checkingNickname = ref(false)
const checkingEmail = ref(false)

// ── CAPTCHA state ────────────────────────────────────────────
const challenge = ref<CaptchaChallenge | null>(null)
const captchaLoading = ref(false)
const captchaAnswer = ref('')
const captchaError = ref('')
const captchaToken = ref('')
const captchaSelected = ref(-1) // for selection-based challenges

// ── Code state ───────────────────────────────────────────────
const code = ref('')
const codeError = ref('')
const codeLoading = ref(false)
const cooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null
const registerToken = ref('')
const resendToken = ref('')

// ── Success state ────────────────────────────────────────────
const successUser = ref('')
const successEmail = ref('')
const successAccount = ref('')

// ── Password strength ────────────────────────────────────────

const passwordStrength = computed(() => {
  const pw = password.value
  if (!pw) return { level: 0, label: '', color: '', width: '0%' }
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  // Normalize to 0-4
  if (score <= 1) return { level: 1, label: '弱', color: 'var(--danger)', width: '25%' }
  if (score <= 2) return { level: 2, label: '中', color: '#e6a817', width: '50%' }
  if (score <= 3) return { level: 3, label: '强', color: 'var(--grass-dark)', width: '75%' }
  return { level: 4, label: '非常强', color: '#2e7d32', width: '100%' }
})

// ── Helpers ──────────────────────────────────────────────────

function clearErrors() {
  formErrors.nickname = ''
  formErrors.email = ''
  formErrors.password = ''
  formErrors.confirm = ''
}

function validateForm(): boolean {
  clearErrors()
  let ok = true
  if (!nickname.value.trim()) {
    formErrors.nickname = '请输入昵称'
    ok = false
  } else if (nickname.value.trim().length < 2) {
    formErrors.nickname = '昵称至少 2 个字符'
    ok = false
  }
  if (!email.value.trim()) {
    formErrors.email = '请输入邮箱'
    ok = false
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    formErrors.email = '邮箱格式不正确'
    ok = false
  }
  if (!password.value) {
    formErrors.password = '请输入密码'
    ok = false
  } else if (password.value.length < 4) {
    formErrors.password = '密码至少 4 个字符'
    ok = false
  }
  if (!confirmPassword.value) {
    formErrors.confirm = '请再次输入密码'
    ok = false
  } else if (password.value !== confirmPassword.value) {
    formErrors.confirm = '两次密码输入不一致'
    ok = false
  }
  return ok
}

// ── Step 0 → 1: Start verification ──────────────────────────

async function startVerification() {
  if (!validateForm()) return

  // Check nickname availability
  checkingNickname.value = true
  try {
    const nickResult = await checkNicknameAvailable(nickname.value.trim())
    if (!nickResult.available) {
      formErrors.nickname = '该昵称已被使用'
      checkingNickname.value = false
      return
    }
  } catch { /* ignore, server will validate */ }
  checkingNickname.value = false

  // Load CAPTCHA
  await loadCaptcha()
}

async function loadCaptcha() {
  captchaLoading.value = true
  captchaError.value = ''
  captchaAnswer.value = ''
  captchaSelected.value = -1
  try {
    challenge.value = await fetchCaptcha()
    step.value = 'captcha'
  } catch (e: any) {
    captchaError.value = e?.response?.data?.detail || '获取验证失败，请重试'
  } finally {
    captchaLoading.value = false
  }
}

// ── Step 1 → 2: Submit CAPTCHA → send code ──────────────────

function getCaptchaAnswer(): string | null {
  if (!challenge.value) return null
  switch (challenge.value.type) {
    case 'math':
      return captchaAnswer.value.trim() || null
    case 'emoji':
    case 'color':
      return captchaSelected.value >= 0 ? String(captchaSelected.value) : null
    default:
      return null
  }
}

async function submitCaptcha() {
  const answer = getCaptchaAnswer()
  if (answer === null) {
    captchaError.value = '请完成验证'
    return
  }
  if (!challenge.value) return

  captchaLoading.value = true
  captchaError.value = ''

  try {
    // Verify CAPTCHA
    const verifyResult = await verifyCaptcha(challenge.value.id, answer)
    captchaToken.value = verifyResult.captcha_token

    // Send code to email
    const sendResult = await sendVerificationCode(email.value.trim(), captchaToken.value)
    resendToken.value = sendResult.resend_token || ''
    step.value = 'code'
    startCooldown(sendResult.cooldown || 30)
  } catch (e: any) {
    captchaError.value = e?.response?.data?.detail || '验证失败，请重试'
    // Reload CAPTCHA on failure
    await loadCaptcha()
  } finally {
    captchaLoading.value = false
  }
}

// ── Cooldown timer ──────────────────────────────────────────

function startCooldown(seconds: number) {
  cooldown.value = seconds
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    if (cooldown.value > 0) {
      cooldown.value--
    } else {
      if (cooldownTimer) clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

// ── Step 2: Resend code ─────────────────────────────────────

async function resendCode() {
  if (cooldown.value > 0) return
  codeError.value = ''
  codeLoading.value = true

  try {
    if (resendToken.value) {
      const result = await resendVerificationCode(email.value.trim(), resendToken.value)
      startCooldown(result.cooldown || 30)
    } else {
      // Fallback: need a new captcha
      await loadCaptcha()
      if (!challenge.value) return
      step.value = 'captcha'
      captchaError.value = '请重新验证以发送验证码'
    }
  } catch (e: any) {
    // If resend token expired, fall back to captcha
    if (e?.response?.status === 400) {
      await loadCaptcha()
      step.value = 'captcha'
      captchaError.value = '验证已过期，请重新验证'
    } else {
      codeError.value = e?.response?.data?.detail || '发送失败，请稍后重试'
    }
  } finally {
    codeLoading.value = false
  }
}

// ── Step 2 → 3: Verify code → register → success ───────────

async function submitCode() {
  if (!code.value.trim() || code.value.trim().length !== 6) {
    codeError.value = '请输入 6 位验证码'
    return
  }

  codeLoading.value = true
  codeError.value = ''

  try {
    // Verify code
    const verifyResult = await verifyEmailCode(email.value.trim(), code.value.trim())
    registerToken.value = verifyResult.register_token

    // Complete registration
    const result = await auth.registerWithEmail(
      nickname.value.trim(),
      email.value.trim(),
      password.value,
      registerToken.value,
    )

    if (result.ok) {
      successUser.value = nickname.value.trim()
      successEmail.value = email.value.trim()
      successAccount.value = `U${String(result.userId).padStart(5, '0')}`
      step.value = 'success'
    } else {
      codeError.value = auth.error || '注册失败，请重试'
    }
  } catch (e: any) {
    codeError.value = e?.response?.data?.detail || '验证失败，请重试'
  } finally {
    codeLoading.value = false
  }
}

// ── Step 3: Go to home ──────────────────────────────────────

function goHome() {
  router.push('/')
}

// ── Cleanup ──────────────────────────────────────────────────

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})

// ── CAPTCHA option click ────────────────────────────────────

function selectOption(index: number) {
  if (captchaLoading.value) return
  captchaSelected.value = index
  captchaError.value = ''
}

// ── Emit to parent ──────────────────────────────────────────

const emit = defineEmits<{
  switchMode: [mode: 'login']
}>()

function goToLogin() {
  emit('switchMode', 'login')
}

/** Helper: get options array from captcha data (safe for template) */
function captchaOptions(): string[] {
  const d = challenge.value?.data
  if (d && 'options' in d) return d.options as string[]
  return []
}
</script>

<template>
  <div class="register-flow">
    <!-- ═══════════ Step: Form ═══════════ -->
    <template v-if="step === 'form' || step === 'success'">
      <div v-show="step === 'form'">
        <form class="auth-form" @submit.prevent="startVerification">
          <div class="field">
            <label for="reg-nickname">昵称</label>
            <input
              id="reg-nickname"
              v-model="nickname"
              type="text"
              placeholder="输入昵称"
              autocomplete="off"
              :disabled="checkingNickname"
              @input="formErrors.nickname = ''"
            />
            <p v-if="formErrors.nickname" class="field-error">{{ formErrors.nickname }}</p>
          </div>

          <div class="field">
            <label for="reg-email">邮箱</label>
            <input
              id="reg-email"
              v-model="email"
              type="email"
              placeholder="输入邮箱地址"
              autocomplete="email"
              :disabled="checkingEmail"
              @input="formErrors.email = ''"
            />
            <p v-if="formErrors.email" class="field-error">{{ formErrors.email }}</p>
          </div>

          <div class="field">
            <label for="reg-password">密码</label>
            <div class="pw-field">
              <input
                id="reg-password"
                v-model="password"
                :type="showPw ? 'text' : 'password'"
                placeholder="输入密码（至少 4 位）"
                autocomplete="new-password"
                @input="formErrors.password = ''"
              />
              <button type="button" class="pw-toggle" @click="showPw = !showPw" tabindex="-1">
                {{ showPw ? '🙈' : '👁️' }}
              </button>
            </div>
            <div v-if="password" class="strength-bar-wrap">
              <div class="strength-bar" :style="{ width: passwordStrength.width, backgroundColor: passwordStrength.color }"></div>
            </div>
            <div v-if="password" class="strength-label" :style="{ color: passwordStrength.color }">
              密码强度：{{ passwordStrength.label }}
            </div>
            <p v-if="formErrors.password" class="field-error">{{ formErrors.password }}</p>
          </div>

          <div class="field">
            <label for="reg-confirm">确认密码</label>
            <div class="pw-field">
              <input
                id="reg-confirm"
                v-model="confirmPassword"
                :type="showConfirm ? 'text' : 'password'"
                placeholder="再次输入密码"
                autocomplete="new-password"
                @input="formErrors.confirm = ''"
              />
              <button type="button" class="pw-toggle" @click="showConfirm = !showConfirm" tabindex="-1">
                {{ showConfirm ? '🙈' : '👁️' }}
              </button>
            </div>
            <p v-if="formErrors.confirm" class="field-error">{{ formErrors.confirm }}</p>
          </div>

          <p v-if="auth.error" class="auth-error">⚠ {{ auth.error }}</p>

          <button
            type="submit"
            class="btn btn-primary btn-block"
            :disabled="checkingNickname || checkingEmail"
          >
            {{ checkingNickname || checkingEmail ? '验证中...' : '邮箱验证' }}
          </button>
        </form>
      </div>
    </template>

    <!-- ═══════════ Step: CAPTCHA ═══════════ -->
    <template v-if="step === 'captcha'">
      <div class="step-header">
        <button class="back-btn" @click="step = 'form'" :disabled="captchaLoading">← 返回</button>
        <h3>② 真人验证</h3>
      </div>

      <div v-if="captchaLoading" class="captcha-loading">加载验证中...</div>

      <div v-else-if="challenge" class="captcha-body">
        <!-- Math CAPTCHA -->
        <template v-if="challenge.type === 'math'">
          <p class="captcha-question">{{ challenge.data.question }}</p>
          <input
            v-model="captchaAnswer"
            type="text"
            inputmode="numeric"
            class="captcha-input"
            placeholder="输入答案"
            @keyup.enter="submitCaptcha"
          />
        </template>

        <!-- Emoji CAPTCHA -->
        <template v-else-if="challenge.type === 'emoji'">
          <p class="captcha-question">{{ challenge.data.question }}</p>
          <div class="emoji-grid">
            <button
              v-for="(opt, i) in captchaOptions()"
              :key="i"
              class="emoji-btn"
              :class="{ selected: captchaSelected === i }"
              @click="selectOption(i)"
            >
              {{ opt }}
            </button>
          </div>
        </template>

        <!-- Color CAPTCHA -->
        <template v-else-if="challenge.type === 'color'">
          <p class="captcha-question">{{ challenge.data.question }}</p>
          <div class="color-grid">
            <button
              v-for="(opt, i) in captchaOptions()"
              :key="i"
              class="color-btn"
              :class="{ selected: captchaSelected === i }"
              :style="{
                backgroundColor: opt,
                color: ['白色','黄色','粉色'].includes(opt) ? '#333' : '#fff',
              }"
              @click="selectOption(i)"
            >
              {{ opt }}
            </button>
          </div>
        </template>

        <p v-if="captchaError" class="auth-error">⚠ {{ captchaError }}</p>

        <button
          class="btn btn-primary btn-block"
          :disabled="captchaLoading || (!captchaAnswer.trim() && captchaSelected < 0)"
          @click="submitCaptcha"
        >
          {{ captchaLoading ? '验证中...' : '确认验证' }}
        </button>
      </div>
    </template>

    <!-- ═══════════ Step: Code ═══════════ -->
    <template v-if="step === 'code'">
      <div class="step-header">
        <button class="back-btn" @click="step = 'captcha'" :disabled="codeLoading">← 返回</button>
        <h3>③ 邮箱验证</h3>
      </div>

      <p class="code-hint">
        验证码已发送至 <strong>{{ email }}</strong>
      </p>

      <div class="code-input-area">
        <input
          v-model="code"
          type="text"
          inputmode="numeric"
          maxlength="6"
          class="code-input"
          placeholder="输入 6 位验证码"
          autocomplete="one-time-code"
          @keyup.enter="submitCode"
        />
      </div>

      <button
        class="btn btn-outline btn-block btn-sm"
        :disabled="cooldown > 0 || codeLoading"
        @click="resendCode"
      >
        {{ cooldown > 0 ? `${cooldown}s 后可重新发送` : '重新发送' }}
      </button>

      <p v-if="codeError" class="auth-error">⚠ {{ codeError }}</p>

      <button
        class="btn btn-primary btn-block"
        :disabled="code.length !== 6 || codeLoading"
        @click="submitCode"
      >
        {{ codeLoading ? '验证中...' : '确认注册' }}
      </button>
    </template>

    <!-- ═══════════ Step: Success ═══════════ -->
    <template v-if="step === 'success'">
      <div class="success-step">
        <div class="success-icon">✅</div>
        <h3>注册成功！</h3>

        <div class="success-card">
          <div class="success-row">
            <span class="success-label">账号</span>
            <span class="success-value account-code">{{ successAccount }}</span>
          </div>
          <div class="success-row">
            <span class="success-label">昵称</span>
            <span class="success-value">{{ successUser }}</span>
          </div>
          <div class="success-row">
            <span class="success-label">邮箱</span>
            <span class="success-value">{{ successEmail }}</span>
          </div>
        </div>

        <p class="success-tip">您已登录，可以开始学习啦！</p>

        <button class="btn btn-primary btn-block" @click="goHome">
          开始学习 →
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ── Step header ─────────────────────── */
.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.step-header h3 {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text);
}
.back-btn {
  background: none;
  border: 2px solid var(--wood-light);
  color: var(--text-light);
  padding: 4px 10px;
  cursor: pointer;
  font-family: inherit;
  font-size: 0.75rem;
}
.back-btn:hover:not(:disabled) {
  border-color: var(--golden);
  color: var(--golden);
}
.back-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Form fields ─────────────────────── */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text);
}
.field input {
  font-family: inherit;
  font-size: 0.95rem;
  padding: 10px 12px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
  transition: border-color 0.05s step-start;
}
.field input:focus {
  border-color: var(--golden);
}
.field input:disabled {
  opacity: 0.5;
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
.field-error {
  color: var(--danger);
  font-size: 0.75rem;
  margin: 0;
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
  transition: color 0.2s ease;
}

/* ── CAPTCHA ─────────────────────────── */
.captcha-loading {
  text-align: center;
  padding: 40px 0;
  color: var(--text-light);
  font-size: 0.85rem;
}
.captcha-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.captcha-question {
  text-align: center;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  padding: 12px;
  background: var(--bg-hover);
  border: 2px solid var(--wood-light);
}
.captcha-input {
  text-align: center;
  font-size: 1.2rem;
  padding: 12px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
  font-family: inherit;
}
.captcha-input:focus {
  border-color: var(--golden);
}

/* Emoji grid */
.emoji-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.emoji-btn {
  font-size: 2.5rem;
  padding: 16px;
  background: var(--cream);
  border: 3px solid var(--wood-light);
  cursor: pointer;
  transition: all 0.05s step-start;
  text-align: center;
}
.emoji-btn:hover {
  border-color: var(--golden);
  transform: scale(1.05);
}
.emoji-btn.selected {
  border-color: var(--golden);
  background: var(--bg-hover);
  box-shadow: 0 0 0 3px rgba(200, 160, 80, 0.3);
}

/* Color grid */
.color-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.color-btn {
  font-size: 0.95rem;
  font-weight: 600;
  padding: 16px;
  border: 3px solid transparent;
  cursor: pointer;
  transition: all 0.05s step-start;
  text-align: center;
  font-family: inherit;
}
.color-btn:hover {
  transform: scale(1.03);
}
.color-btn.selected {
  border-color: var(--golden);
  box-shadow: 0 0 0 3px rgba(200, 160, 80, 0.4);
}

/* ── Code input ──────────────────────── */
.code-hint {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-light);
  margin-bottom: 16px;
}
.code-input-area {
  margin-bottom: 12px;
}
.code-input {
  display: block;
  width: 100%;
  text-align: center;
  font-size: 1.5rem;
  letter-spacing: 8px;
  padding: 14px 12px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
  font-family: monospace;
}
.code-input:focus {
  border-color: var(--golden);
}

/* ── Success ─────────────────────────── */
.success-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.success-icon {
  font-size: 3rem;
}
.success-step h3 {
  font-size: 1.1rem;
  color: var(--text);
  margin: 0;
}
.success-card {
  width: 100%;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  padding: 16px;
}
.success-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px dashed var(--wood-light);
}
.success-row:last-child {
  border-bottom: none;
}
.success-label {
  color: var(--text-light);
  font-size: 0.85rem;
}
.success-value {
  color: var(--text);
  font-weight: 600;
  font-size: 0.9rem;
}
.account-code {
  font-family: 'Press Start 2P', monospace;
  font-size: 0.7rem;
  color: var(--golden);
  letter-spacing: 1px;
}
.success-tip {
  color: var(--grass-light);
  font-size: 0.85rem;
  margin: 0;
}

/* ── Shared ──────────────────────────── */
.auth-error {
  color: var(--danger);
  font-size: 0.85rem;
  text-align: center;
  padding: 8px;
  background: rgba(208, 80, 80, 0.08);
  border: 2px solid var(--danger);
}
.btn-block {
  width: 100%;
  justify-content: center;
}
.btn-sm {
  font-size: 0.75rem;
  padding: 8px;
}
</style>
