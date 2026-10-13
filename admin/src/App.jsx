import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken, getSessionUser } from './api.js'
import Login from './Login.jsx'
import Layout from './Layout.jsx'
import Dashboard from './Dashboard.jsx'
import Users from './Users.jsx'
import Organizations from './Organizations.jsx'
import Runs from './Runs.jsx'

function Protected() {
  if (!getToken()) return <Navigate to="/login" replace />
  return <Layout />
}

export default function App() {
  const user = getSessionUser()
  return (
    <Routes>
      <Route path="/login" element={getToken() ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<Protected />}>
        <Route path="/" element={<Dashboard user={user} />} />
        <Route path="/users" element={<Users />} />
        <Route path="/organizations" element={<Organizations />} />
        <Route path="/runs" element={<Runs />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}