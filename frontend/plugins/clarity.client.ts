import Clarity from '@microsoft/clarity'

export default defineNuxtPlugin(() => {
  const clarityId = useRuntimeConfig().public.clarityId
  if (!clarityId) return
  Clarity.init(clarityId)
})
