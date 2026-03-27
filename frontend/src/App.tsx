import { Router, Route } from '@solidjs/router';
import { BestBuys } from './views/BestBuys';
import { NorwayArbitrage } from './views/NorwayArbitrage';
import { YourTaste } from './views/YourTaste';
import { WildCards } from './views/WildCards';
import { EndingSoon } from './views/EndingSoon';
import { Watchlist } from './views/Watchlist';
import { LotDetailPage } from './views/LotDetailPage';
import './styles.css';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  component: () => JSX.Element;
}

const navItems: NavItem[] = [
  {
    path: '/',
    label: 'Best Buys',
    icon: '⭐',
    component: BestBuys,
  },
  {
    path: '/norway',
    label: 'Norway Arbitrage',
    icon: '🇳🇴',
    component: NorwayArbitrage,
  },
  {
    path: '/taste',
    label: 'Your Taste',
    icon: '🎨',
    component: YourTaste,
  },
  {
    path: '/wildcards',
    label: 'Wild Cards',
    icon: '🎲',
    component: WildCards,
  },
  {
    path: '/ending',
    label: 'Ending Soon',
    icon: '⏰',
    component: EndingSoon,
  },
  {
    path: '/watchlist',
    label: 'Watchlist',
    icon: '👁',
    component: Watchlist,
  },
];

export const App = () => {
  return (
    <Router>
      <div class="app-layout">
        <aside class="sidebar">
          <div class="sidebar-header">
            <h1 class="sidebar-title">Auction Vision</h1>
          </div>

          <nav class="sidebar-nav">
            {navItems.map((item) => (
              <a
                href={item.path}
                class="nav-item"
                activeClass="active"
              >
                <span class="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </a>
            ))}
          </nav>
        </aside>

        <main class="main-content">
          <Route path="/" component={BestBuys} />
          <Route path="/norway" component={NorwayArbitrage} />
          <Route path="/taste" component={YourTaste} />
          <Route path="/wildcards" component={WildCards} />
          <Route path="/ending" component={EndingSoon} />
          <Route path="/watchlist" component={Watchlist} />
          <Route path="/lots/:id" component={LotDetailPage} />
        </main>
      </div>
    </Router>
  );
};
