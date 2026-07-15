<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import RegisterFlow from '@/components/RegisterFlow.vue'
import {
  fetchCaptcha,
  verifyCaptcha,
  forgotPasswordSendCode,
  forgotPasswordReset,
} from '@/api'
import type { CaptchaChallenge } from '@/types'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

// ── Mode ─────────────────────────────────────────────────────
type PageMode = 'login' | 'register' | 'forgot-password'
const mode = ref<PageMode>('login')

function switchMode(m: PageMode) {
  mode.value = m
  auth.error = null
  forgotStep.value = 'email'
  loginShowCaptcha.value = false
}

// ── Login state ──────────────────────────────────────────────
const username = ref('')
const password = ref('')
const submitting = ref(false)
const loginShowCaptcha = ref(false)
const loginRemember = ref(true)
const showLoginPw = ref(false)
const loginChallenge = ref<CaptchaChallenge | null>(null)
const loginCaptchaAnswer = ref('')
const loginCaptchaSelected = ref(-1)
const loginCaptchaToken = ref('')

async function handleLogin() {
  if (!username.value.trim() || !password.value.trim()) return
  submitting.value = true
  auth.error = null

  const result = await auth.login(
    username.value.trim(),
    password.value.trim(),
    loginCaptchaToken.value || undefined,
    loginRemember.value,
  )

  submitting.value = false

  // Need captcha
  if (result.captcha_required) {
    loginShowCaptcha.value = true
    await loadLoginCaptcha()
    return
  }

  if (result.ok) {
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  }
}

async function loadLoginCaptcha() {
  try {
    loginChallenge.value = await fetchCaptcha()
    loginCaptchaAnswer.value = ''
    loginCaptchaSelected.value = -1
  } catch {
    auth.error = '获取验证失败'
  }
}

function selectLoginCaptcha(index: number) {
  loginCaptchaSelected.value = index
}

function getLoginCaptchaAnswer(): string | null {
  if (!loginChallenge.value) return null
  const t = loginChallenge.value.type
  if (t === 'math') return loginCaptchaAnswer.value.trim() || null
  if (t === 'emoji' || t === 'color') return loginCaptchaSelected.value >= 0 ? String(loginCaptchaSelected.value) : null
  return null
}

async function submitLoginCaptcha() {
  if (!loginChallenge.value) return
  const answer = getLoginCaptchaAnswer()
  if (answer === null) {
    auth.error = '请完成验证'
    return
  }

  try {
    const result = await verifyCaptcha(loginChallenge.value.id, answer)
    loginCaptchaToken.value = result.captcha_token
    // Retry login
    await handleLogin()
  } catch (e: any) {
    auth.error = e?.response?.data?.detail || '验证失败'
    await loadLoginCaptcha()
  }
}

// ── Forgot password state ────────────────────────────────────
type ForgotStep = 'email' | 'captcha' | 'code' | 'newpass' | 'success'
const forgotStep = ref<ForgotStep>('email')
const forgotEmail = ref('')
const forgotChallenge = ref<CaptchaChallenge | null>(null)
const forgotCaptchaToken = ref('')
const forgotCode = ref('')
const forgotNewPassword = ref('')
const forgotConfirmPassword = ref('')
const forgotCooldown = ref(0)
const forgotError = ref('')
const forgotLoading = ref(false)

function startForgot() {
  forgotStep.value = 'email'
  forgotEmail.value = ''
  forgotCaptchaToken.value = ''
  forgotCode.value = ''
  forgotNewPassword.value = ''
  forgotConfirmPassword.value = ''
  forgotCooldown.value = 0
  forgotError.value = ''
  forgotChallenge.value = null
  auth.error = null
}

async function forgotSubmitEmail() {
  if (!forgotEmail.value.trim()) {
    forgotError.value = '请输入邮箱'
    return
  }
  forgotLoading.value = true
  forgotError.value = ''

  try {
    forgotChallenge.value = await fetchCaptcha()
    forgotStep.value = 'captcha'
  } catch {
    forgotError.value = '获取验证失败'
  } finally {
    forgotLoading.value = false
  }
}

async function forgotSubmitCaptcha() {
  if (!forgotChallenge.value) return

  const answer = forgotChallenge.value.type === 'math'
    ? forgotCaptchaAnswer.value.trim()
    : forgotCaptchaSelected.value >= 0 ? String(forgotCaptchaSelected.value) : null

  if (answer === null) {
    forgotError.value = '请完成验证'
    return
  }

  forgotLoading.value = true
  forgotError.value = ''

  try {
    const result = await verifyCaptcha(forgotChallenge.value.id, answer)
    const captchaToken = result.captcha_token

    // Send code
    const sendResult = await forgotPasswordSendCode(forgotEmail.value.trim(), captchaToken)
    forgotCooldown.value = sendResult.cooldown || 30
    forgotStep.value = 'code'
    startForgotCooldown()
  } catch (e: any) {
    forgotError.value = e?.response?.data?.detail || '发送失败'
    // Reload captcha
    forgotChallenge.value = await fetchCaptcha()
    forgotCaptchaAnswer.value = ''
    forgotCaptchaSelected.value = -1
  } finally {
    forgotLoading.value = false
  }
}

let forgotCooldownTimer: ReturnType<typeof setInterval> | null = null
const forgotCaptchaAnswer = ref('')
const forgotCaptchaSelected = ref(-1)

function startForgotCooldown() {
  if (forgotCooldownTimer) clearInterval(forgotCooldownTimer)
  forgotCooldownTimer = setInterval(() => {
    if (forgotCooldown.value > 0) {
      forgotCooldown.value--
    } else {
      if (forgotCooldownTimer) clearInterval(forgotCooldownTimer)
    }
  }, 1000)
}

onUnmounted(() => {
  if (forgotCooldownTimer) clearInterval(forgotCooldownTimer)
  forgotCooldownTimer = null
})

async function forgotSubmitCode() {
  if (!forgotCode.value.trim() || forgotCode.value.trim().length !== 6) {
    forgotError.value = '请输入 6 位验证码'
    return
  }
  forgotStep.value = 'newpass'
  forgotError.value = ''
}

async function forgotSubmitNewPassword() {
  if (!forgotNewPassword.value || forgotNewPassword.value.length < 4) {
    forgotError.value = '密码至少 4 个字符'
    return
  }
  if (forgotNewPassword.value !== forgotConfirmPassword.value) {
    forgotError.value = '两次密码输入不一致'
    return
  }

  forgotLoading.value = true
  forgotError.value = ''

  try {
    const result = await forgotPasswordReset(
      forgotEmail.value.trim(),
      forgotCode.value.trim(),
      forgotNewPassword.value,
    )
    if (result.success) {
      forgotStep.value = 'success'
    } else {
      forgotError.value = result.message || '重置失败'
    }
  } catch (e: any) {
    forgotError.value = e?.response?.data?.detail || '重置失败，验证码可能已过期'
    forgotStep.value = 'code'
  } finally {
    forgotLoading.value = false
  }
}

function forgotGoToLogin() {
  if (forgotCooldownTimer) clearInterval(forgotCooldownTimer)
  forgotCooldownTimer = null
  switchMode('login')
}

function selectForgotCaptcha(index: number) {
  forgotCaptchaSelected.value = index
}
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="card-stripe"></div>
      <h1 class="login-title">🌾 日本語学習</h1>

      <!-- ════════════════ Tabs ════════════════ -->
      <div v-if="mode !== 'forgot-password'" class="auth-tabs">
        <button class="auth-tab" :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
        <button class="auth-tab" :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
      </div>

      <!-- ════════════════ LOGIN ════════════════ -->
      <template v-if="mode === 'login'">
        <form class="auth-form" @submit.prevent="handleLogin">
          <div class="field">
            <label for="username">用户名 / 邮箱</label>
            <input id="username" v-model="username" type="text" placeholder="输入用户名或邮箱"
              autocomplete="username" :disabled="submitting" required />
          </div>
          <div class="field">
            <label for="password">密码</label>
            <div class="pw-field">
              <input id="password" v-model="password"
                :type="showLoginPw ? 'text' : 'password'" placeholder="输入密码"
                autocomplete="current-password" :disabled="submitting" required />
              <button type="button" class="pw-toggle" @click="showLoginPw = !showLoginPw" tabindex="-1">
                {{ showLoginPw ? '🙈' : '👁️' }}
              </button>
            </div>
          </div>

          <!-- Captcha inline (after 3 failures) -->
          <div v-if="loginShowCaptcha && loginChallenge" class="login-captcha-box">
            <p class="captcha-hint">登录失败次数过多，请完成验证</p>
            <!-- Math -->
            <template v-if="loginChallenge.type === 'math'">
              <p class="captcha-question-sm">{{ loginChallenge.data.question }}</p>
              <input v-model="loginCaptchaAnswer" type="text" inputmode="numeric"
                class="captcha-input-sm" placeholder="答案" />
            </template>
            <!-- Emoji / Color -->
            <template v-else>
              <p class="captcha-question-sm">{{ loginChallenge.data.question }}</p>
              <div class="captcha-options-sm">
                <button v-for="(opt, i) in ('options' in loginChallenge.data ? loginChallenge.data.options : [])"
                  :key="i" class="captcha-opt-btn"
                  :class="{ selected: loginCaptchaSelected === i }"
                  @click="selectLoginCaptcha(i)">{{ opt }}</button>
              </div>
            </template>
            <button type="button" class="btn btn-sm btn-primary btn-block"
              :disabled="!getLoginCaptchaAnswer()" @click="submitLoginCaptcha">
              验证后登录
            </button>
          </div>

          <label class="remember-label">
            <input type="checkbox" v-model="loginRemember" class="remember-checkbox" />
            <span>记住登录状态</span>
          </label>

          <p v-if="auth.error && !loginShowCaptcha" class="auth-error">⚠ {{ auth.error }}</p>

          <button type="submit" class="btn btn-primary btn-block"
            :disabled="submitting || !username.trim() || !password.trim()">
            {{ submitting ? '登录中...' : loginShowCaptcha ? '验证后登录' : '登录' }}
          </button>
        </form>

        <p class="auth-hint">
          <button class="link-btn" @click="switchMode('forgot-password')">忘记密码？</button>
        </p>
      </template>

      <!-- ════════════════ REGISTER ════════════════ -->
      <RegisterFlow v-else-if="mode === 'register'" @switch-mode="switchMode" />

      <!-- ════════════════ FORGOT PASSWORD ════════════════ -->
      <template v-else-if="mode === 'forgot-password'">
        <div class="forgot-header">
          <button class="back-btn" @click="switchMode('login')">← 返回</button>
          <h3>找回密码</h3>
        </div>

        <!-- Step: Email -->
        <template v-if="forgotStep === 'email'">
          <p class="forgot-desc">输入注册时使用的邮箱，我们将发送验证码</p>
          <form class="auth-form" @submit.prevent="forgotSubmitEmail">
            <div class="field">
              <label for="forgot-email">邮箱</label>
              <input id="forgot-email" v-model="forgotEmail" type="email"
                placeholder="输入注册邮箱" autocomplete="email" />
            </div>
            <p v-if="forgotError" class="auth-error">⚠ {{ forgotError }}</p>
            <button type="submit" class="btn btn-primary btn-block"
              :disabled="forgotLoading || !forgotEmail.trim()">
              {{ forgotLoading ? '处理中...' : '发送验证码' }}
            </button>
          </form>
        </template>

        <!-- Step: Captcha -->
        <template v-if="forgotStep === 'captcha' && forgotChallenge">
          <p class="forgot-desc">请完成真人验证</p>
          <template v-if="forgotChallenge.type === 'math'">
            <p class="captcha-question-sm">{{ forgotChallenge.data.question }}</p>
            <input v-model="forgotCaptchaAnswer" type="text" inputmode="numeric"
              class="captcha-input-sm" placeholder="答案" />
          </template>
          <template v-else>
            <p class="captcha-question-sm">{{ forgotChallenge.data.question }}</p>
            <div class="captcha-options-sm">
              <button v-for="(opt, i) in ('options' in forgotChallenge.data ? forgotChallenge.data.options : [])"
                :key="i" class="captcha-opt-btn"
                :class="{ selected: forgotCaptchaSelected === i }"
                @click="selectForgotCaptcha(i)">{{ opt }}</button>
            </div>
          </template>
          <p v-if="forgotError" class="auth-error">⚠ {{ forgotError }}</p>
          <button class="btn btn-primary btn-block"
            :disabled="forgotLoading || (!forgotCaptchaAnswer.trim() && forgotCaptchaSelected < 0)"
            @click="forgotSubmitCaptcha">
            {{ forgotLoading ? '发送中...' : '确认' }}
          </button>
        </template>

        <!-- Step: Code -->
        <template v-if="forgotStep === 'code'">
          <p class="forgot-desc">验证码已发送至 <strong>{{ forgotEmail }}</strong></p>
          <input v-model="forgotCode" type="text" inputmode="numeric" maxlength="6"
            class="code-input" placeholder="输入 6 位验证码"
            @keyup.enter="forgotSubmitCode" />
          <p v-if="forgotError" class="auth-error">⚠ {{ forgotError }}</p>
          <button class="btn btn-primary btn-block"
            :disabled="forgotCode.length !== 6" @click="forgotSubmitCode">下一步</button>
        </template>

        <!-- Step: New password -->
        <template v-if="forgotStep === 'newpass'">
          <p class="forgot-desc">设置新密码</p>
          <form class="auth-form" @submit.prevent="forgotSubmitNewPassword">
            <div class="field">
              <label for="newpass">新密码</label>
              <input id="newpass" v-model="forgotNewPassword" type="password"
                placeholder="至少 4 位" autocomplete="new-password" />
            </div>
            <div class="field">
              <label for="confirmpass">确认密码</label>
              <input id="confirmpass" v-model="forgotConfirmPassword" type="password"
                placeholder="再次输入新密码" autocomplete="new-password" />
            </div>
            <p v-if="forgotError" class="auth-error">⚠ {{ forgotError }}</p>
            <button type="submit" class="btn btn-primary btn-block"
              :disabled="forgotLoading || !forgotNewPassword || forgotNewPassword.length < 4">
              {{ forgotLoading ? '重置中...' : '重置密码' }}
            </button>
          </form>
        </template>

        <!-- Step: Success -->
        <template v-if="forgotStep === 'success'">
          <div class="success-block">
            <div class="success-icon">✅</div>
            <h3>密码已重置</h3>
            <p>请使用新密码登录</p>
            <button class="btn btn-primary btn-block" @click="forgotGoToLogin">去登录</button>
          </div>
        </template>
      </template>

      <!-- Bottom hint -->
      <p v-if="mode !== 'forgot-password'" class="auth-hint">
        {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
        <button class="link-btn" @click="switchMode(mode === 'login' ? 'register' : 'login')">
          {{ mode === 'login' ? '注册' : '登录' }}
        </button>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 120px);
}
.login-card {
  width: 100%;
  max-width: 420px;
  padding: 32px 28px;
  position: relative;
  overflow: hidden;
}
.card-stripe {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--golden), var(--grass-light), var(--pink), var(--golden));
}
.login-title {
  text-align: center;
  font-size: 1.3rem;
  margin-bottom: 24px;
  color: var(--text);
}

/* ── Tabs ──────────────────────────── */
.auth-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 24px;
  border: 3px solid var(--wood-dark);
}
.auth-tab {
  flex: 1;
  font-family: 'Press Start 2P', monospace;
  font-size: 0.5rem;
  padding: 12px;
  background: var(--cream);
  color: var(--wood-dark);
  border: none;
  cursor: pointer;
  transition: all 0.05s step-start;
}
.auth-tab.active {
  background: var(--wood-dark);
  color: var(--cream);
}
.auth-tab:not(.active):hover {
  background: var(--bg-hover);
}

/* ── Form ──────────────────────────── */
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
.auth-hint {
  text-align: center;
  margin-top: 16px;
  font-size: 0.8rem;
  color: var(--text-light);
}
.link-btn {
  background: none;
  border: none;
  color: var(--golden);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  text-decoration: underline;
  padding: 0;
}
.link-btn:hover {
  color: var(--warm-orange);
}

/* ── Login captcha ─────────────────── */
.login-captcha-box {
  border: 3px solid var(--pink);
  padding: 12px;
  background: rgba(208, 80, 80, 0.05);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.captcha-hint {
  font-size: 0.75rem;
  color: var(--danger);
  text-align: center;
  margin: 0;
}
.captcha-question-sm {
  text-align: center;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text);
  padding: 8px;
  background: var(--bg-hover);
  border: 2px solid var(--wood-light);
  margin: 0;
}
.captcha-input-sm {
  text-align: center;
  font-size: 1.1rem;
  padding: 8px;
  border: 3px solid var(--wood-light);
  background: var(--cream);
  color: var(--text);
  outline: none;
  font-family: inherit;
}
.captcha-input-sm:focus {
  border-color: var(--golden);
}
.captcha-options-sm {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}
.captcha-opt-btn {
  font-size: 1.3rem;
  padding: 8px;
  background: var(--cream);
  border: 3px solid var(--wood-light);
  cursor: pointer;
  text-align: center;
  transition: all 0.05s step-start;
}
.captcha-opt-btn:hover {
  border-color: var(--golden);
}
.captcha-opt-btn.selected {
  border-color: var(--golden);
  background: var(--bg-hover);
  box-shadow: 0 0 0 3px rgba(200, 160, 80, 0.3);
}
.captcha-opt-btn.color-type {
  font-size: 0.85rem;
  font-weight: 600;
}

/* ── Forgot password ───────────────── */
.forgot-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.forgot-header h3 {
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
.back-btn:hover {
  border-color: var(--golden);
  color: var(--golden);
}
.forgot-desc {
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-light);
  margin-bottom: 16px;
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
  box-sizing: border-box;
}
.code-input:focus {
  border-color: var(--golden);
}

/* ── Success ───────────────────────── */
.success-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 0;
}
.success-icon {
  font-size: 3rem;
}
.success-block h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text);
}
.success-block p {
  color: var(--text-light);
  font-size: 0.85rem;
  margin: 0;
}

.btn-sm {
  font-size: 0.75rem;
  padding: 8px;
}

/* ── Remember checkbox ────────────── */
.remember-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--text-light);
  cursor: pointer;
  user-select: none;
}
.remember-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--golden);
  cursor: pointer;
}
</style>
