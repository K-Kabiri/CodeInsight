import { createContext } from 'react'

// Kept in its own file so the provider component file and the hook
// file each export only what react-refresh can handle.
export const AuthContext = createContext(null)
