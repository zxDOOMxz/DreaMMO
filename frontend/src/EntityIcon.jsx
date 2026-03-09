import React from 'react';

function EntityIcon({
  name,
  category,
  iconsIndex,
  resolver,
  className = 'inline-entity-icon',
  fallback = '❓',
  fallbackClassName = '',
  alt,
}) {
  const resolved = typeof resolver === 'function' ? resolver(name) : '';
  const mapped = category && name ? iconsIndex?.[category]?.[name] : '';
  const src = resolved || mapped || '';

  if (src) {
    return <img src={src} alt={alt || name || 'icon'} className={className} loading="lazy" />;
  }

  if (fallbackClassName) {
    return <span className={fallbackClassName}>{fallback}</span>;
  }

  return <span>{fallback}</span>;
}

export default EntityIcon;
