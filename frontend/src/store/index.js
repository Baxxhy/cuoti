import { defineStore } from 'pinia'
import { clearNotebookViews } from '../utils/learning.js'
import { clearTaskDrafts } from '../utils/task-draft.js'
import { getData, postData } from '../api/index.js'

export const roleHome = (role) =>
  ({
    admin: '/pages/admin/workbench',
  })[role] || '/pages/index/index'

/** @typedef {{id: string, name?: string, email?: string, role?: string, access_token?: string}} AppUser */

export const useAppStore = defineStore('app', {
  state: () => ({
    user: /** @type {AppUser | null} */ (null),
    role: 'student',
    dashboard: null,
    online: true,
  }),
  actions: {
    async login(email, password) {
      const user = await postData('/auth/login', { email, password }, { skipAuthRedirect: true })
      uni.setStorageSync('minddimension_access_token', user.access_token)
      this.user = user
      this.role = user.role || 'student'
      return user
    },
    async register(payload) {
      const user = await postData('/auth/register', payload)
      uni.setStorageSync('minddimension_access_token', user.access_token)
      this.user = user
      this.role = user.role || 'student'
      return user
    },
    async loadUser(options) {
      this.user = await getData('/auth/me', options)
      this.role = this.user?.role || 'student'
      return this.user
    },
    async restoreSession() {
      if (!uni.getStorageSync('minddimension_access_token')) return null
      try {
        return await this.loadUser({ silent: true, skipAuthRedirect: true })
      } catch (_) {
        this.user = null
        this.role = 'student'
        return null
      }
    },
    async loadDashboard() {
      this.dashboard = await getData('/dashboard')
    },
    logout() {
      clearNotebookViews()
      clearTaskDrafts()
      this.user = null
      uni.removeStorageSync('minddimension_access_token')
      uni.reLaunch({ url: '/pages/login/login' })
    },
  },
})
