import { createContext } from 'react'

/**
 * App-level "new project" trigger: the sidebar quick action and the
 * dashboard's buttons all open one shared dialog rendered by the
 * shell, so it works from any page. Splitting the context from the
 * components satisfies eslint-plugin-react-refresh's
 * only-export-components rule (same pattern as auth/context.js).
 */
export const NewProjectContext = createContext(null)
