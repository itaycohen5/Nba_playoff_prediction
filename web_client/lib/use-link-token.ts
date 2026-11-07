'use client';
import { useEffect, useState } from 'react';
export function useLinkToken() {
  const [token,setToken]=useState<string|null>(null);
  useEffect(()=>{
    const value=new URLSearchParams(window.location.hash.slice(1)).get('token')??'';
    window.history.replaceState(null,'',window.location.pathname+window.location.search);
    // Tokens stay in memory. Preserve them across React Strict Mode effect replay.
    void Promise.resolve().then(()=>setToken(previous=>previous??(/^[A-Za-z0-9_-]{43}$/.test(value)?value:'')));
  },[]);
  return token;
}
