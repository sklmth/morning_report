import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { navItems } from '@/content/siteContent';

export function NavBar() {
  const [open, setOpen] = useState(false);
  const closeMenu = () => setOpen(false);

  return (
    <nav className="site-nav" aria-label="主导航">
      <a
        className="site-logo display"
        href="#top"
        onClick={closeMenu}
        aria-label="ATLAS AFTER DARK 首页"
      >
        A/AD
      </a>
      <button
        className="nav-toggle"
        type="button"
        aria-label={open ? '关闭菜单' : '打开菜单'}
        aria-expanded={open}
        aria-controls="primary-links"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <X size={18} /> : <Menu size={18} />}
      </button>
      <div className={`nav-links ${open ? 'is-open' : ''}`} id="primary-links">
        {navItems.map((item, index) => (
          <a className="nav-link" key={item.href} href={item.href} onClick={closeMenu}>
            <span>{item.label}</span>
            <small aria-hidden>{String(index + 1).padStart(2, '0')}</small>
          </a>
        ))}
      </div>
    </nav>
  );
}
