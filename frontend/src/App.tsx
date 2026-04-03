import { Router, Route, A } from '@solidjs/router';
import type { ParentProps } from 'solid-js';
import { BestBuys } from './views/BestBuys';
import { Wanted } from './views/Wanted';
import { LotDetailPage } from './views/LotDetailPage';
import './styles.css';

const navItems = [
  { path: '/', label: 'Pipeline', icon: '⭐' },
  { path: '/wanted', label: 'Wanted', icon: '📢' },
];

function Layout(props: ParentProps) {
  return (
    <div class="app-layout">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h1 class="sidebar-title">Auction Vision</h1>
        </div>
        <nav class="sidebar-nav">
          {navItems.map((item) => (
            <A href={item.path} class="nav-item" activeClass="active" end={item.path === '/'}>
              <span class="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </A>
          ))}
        </nav>
      </aside>
      <main class="main-content">
        {props.children}
      </main>
    </div>
  );
}

export const App = () => {
  return (
    <Router root={Layout}>
      <Route path="/" component={BestBuys} />
      <Route path="/wanted" component={Wanted} />
      <Route path="/lots/:id" component={LotDetailPage} />
    </Router>
  );
};
