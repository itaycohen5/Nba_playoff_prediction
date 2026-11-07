'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError, messageOf } from './api';
export function useProtected<T>(load: (signal?: AbortSignal) => Promise<T>) {
  const router = useRouter(), sequence = useRef(0);
  const [data, setData] = useState<T | null>(null), [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const version = ++sequence.current;
    try {
      const result = await load(signal);
      if (version === sequence.current && !signal?.aborted) {setData(result); setError(''); setLoading(false);}
    } catch(e) {
      if (signal?.aborted || version !== sequence.current) return;
      if (e instanceof ApiError && e.status === 401) {
        setData(null);
        router.replace('/login');
      }
      setError(messageOf(e)); setLoading(false);
    }
  }, [load, router]);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.resolve().then(() => {
      if (!controller.signal.aborted) return refresh(controller.signal);
    });
    return () => controller.abort();
  }, [refresh]);
  return {data, error, loading, refresh};
}
