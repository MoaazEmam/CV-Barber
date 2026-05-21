import { create } from 'zustand'

const useAppStore = create((set) => ({
  // Auth
  user: null,
  token: null,
  setAuth: (user, token) => set({ user, token }),
  clearAuth: () => set({ user: null, token: null }),

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
