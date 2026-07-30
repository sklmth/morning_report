import { AboutSection } from '@/components/about/AboutSection';
import { ContactSection } from '@/components/contact/ContactSection';
import { GameSection } from '@/components/game/GameSection';
import { HeroSection } from '@/components/hero/HeroSection';
import { NavBar } from '@/components/layout/NavBar';
import { SiteShell } from '@/components/layout/SiteShell';
import { MusicSection } from '@/components/music/MusicSection';
import { ProjectsSection } from '@/components/projects/ProjectsSection';
import { TravelSection } from '@/components/travel/TravelSection';
import { CustomCursor } from '@/components/visual/CustomCursor';

export function App() {
  return (
    <SiteShell>
      <CustomCursor />
      <div className="home-page">
        <header className="hero" id="top">
          <NavBar />
          <HeroSection />
        </header>
        <main id="main-content">
          <AboutSection />
          <TravelSection />
          <MusicSection />
          <ProjectsSection />
          <GameSection />
          <ContactSection />
        </main>
      </div>
    </SiteShell>
  );
}
