import { useEffect, useState } from 'react';

export function useCurrentTime() {
  const getTime = () => new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date());
  const [time, setTime] = useState(getTime);

  useEffect(() => {
    const timer = window.setInterval(() => setTime(getTime()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  return time;
}
