import { useEffect, useState } from 'react';

export default function useIconIndex() {
  const [iconsIndex, setIconsIndex] = useState({});

  useEffect(() => {
    let cancelled = false;

    fetch('/icons/index.generated.json')
      .then((r) => (r.ok ? r.json() : {}))
      .then((data) => {
        if (!cancelled) {
          setIconsIndex(data || {});
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIconsIndex({});
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return iconsIndex;
}
