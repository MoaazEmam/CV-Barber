import { create } from 'zustand'

const useAppStore = create((set) => ({
  // Auth
  user: null,
  token: null,
  authReady: false,
  setAuth: (user, token) => set({ user, token }),
  setUser: (user) => set({ user }),
  setToken: (token) => set({ token }),
  setAuthReady: (v) => set({ authReady: v }),
  // Clears everything account-scoped, not just credentials — otherwise the
  // next account to sign in (same tab) sees the previous account's CV state.
  clearAuth: () => set({
    user: null,
    token: null,
    masterCvId: null,
    masterCvMeta: null,
    currentApplicationId: null,
    tailoredResult: null,
  }),

  // CV parsing
  masterCvId: null,
  masterCvMeta: null, // { full_name, experience_count, project_count }
  setMasterCv: (id, meta) => set({ masterCvId: id, masterCvMeta: meta }),

  // Tailoring
  currentApplicationId: null,
  tailoredResult: null, // full tailor response
  setTailoredResult: (id, result) => set({ currentApplicationId: id, tailoredResult: result }),

  // Reset CV flow (but keep auth)
  resetCvFlow: () => set({
    masterCvId: null,
    masterCvMeta: null,
    currentApplicationId: null,
    tailoredResult: null,
  }),
}))

export default useAppStore
