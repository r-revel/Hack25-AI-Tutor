export const loginSchema = {
  username: 'required|min:3',
  password: 'required|min:6'
}

export const registerSchema = {
  username: 'required|min:3',
  email: 'required|email',
  password: 'required|min:6'
}