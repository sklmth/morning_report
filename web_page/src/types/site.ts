export type Accent = 'travel' | 'music' | 'game' | 'teal';

export interface NavItem { label: string; href: string; }
export interface Stat { value: string; label: string; }

export interface TravelFrame {
  title: string;
  caption: string;
  tone: 'sky' | 'sunset' | 'green';
}

export interface TravelDestination {
  city: string;
  country: string;
  coordinates: string;
  date: string;
  note: string;
  mood: string;
  track: string;
  color: string;
  region: '北欧' | '亚洲' | '欧洲';
  mapPosition: { x: number; y: number };
  story: string;
  highlights: string[];
  gallery: TravelFrame[];
}

export interface NextStop {
  city: string;
  country: string;
  coordinates: string;
  window: string;
  reason: string;
}

export interface Track {
  id: string;
  title: string;
  artist: string;
  duration: string;
  durationSeconds: number;
  mood: string;
  category: '通勤' | '风景' | '信号' | '协作';
  accent: string;
  story: string;
  tags: string[];
  visualizer: number[];
  src?: string;
}
export type ProjectCategory = '网页体验' | '数据叙事' | '创意实验';
export type ProjectStatus = '上线概念' | '持续进行' | '归档实验';

export interface Project {
  id: string;
  title: string;
  category: ProjectCategory;
  year: string;
  status: ProjectStatus;
  role: string;
  summary: string;
  outcome: string;
  tags: string[];
  accent: string;
}

export interface ContactChannel {
  label: string;
  value: string;
  href?: string;
}

export interface ContactProfile {
  email: string;
  availability: string;
  timezone: string;
  channels: ContactChannel[];
}

export interface GamePathChoice {
  id: string;
  label: string;
  detail: string;
}

export interface GamePlayerPath {
  id: 'spark' | 'echo';
  tone: 'amber' | 'teal';
  label: string;
  title: string;
  copy: string;
  choices: GamePathChoice[];
}

export interface GameRelic {
  id: string;
  name: string;
  description: string;
}

export interface GameChapter {
  id: string;
  index: string;
  title: string;
  realm: string;
  objective: string;
  intro: string;
  paths: [GamePlayerPath, GamePlayerPath];
  solution: { spark: string; echo: string };
  relic: GameRelic;
}
