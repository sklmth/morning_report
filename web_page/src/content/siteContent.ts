import type { ContactProfile, GameChapter, NavItem, NextStop, Project, Stat, Track, TravelDestination } from '@/types/site';

export const navItems: NavItem[] = [
  { label: '关于', href: '#about' },
  { label: '旅行', href: '#travel' },
  { label: '音乐', href: '#music' },
  { label: '项目', href: '#projects' },
  { label: '协作', href: '#co-op' },
  { label: '联系', href: '#contact' },
];

export const stats: Stat[] = [
  { value: '24', label: '收藏在记忆里的城市' },
  { value: '812', label: '留待以后播放的歌曲' },
  { value: '09', label: '一起完成的协作世界' },
];

export const destinations: TravelDestination[] = [
  {
    city: 'Stockholm', country: '瑞典', coordinates: '59.3293° N, 18.0686° E', date: '04.2025',
    note: '蓝调时刻比预想更久，谈话也是。', mood: '群岛 / 安静的光', track: 'The xx — Intro', color: '#69bfe3', region: '北欧', mapPosition: { x: 52, y: 23 },
    story: '渡轮把水面划成平静的线。在南岛的窗边和岛屿的空气之间，这座城市不像目的地，更像一次漫长的呼气。',
    highlights: ['06:42 的渡轮', '雨后的老城', '一件羊毛大衣，三种季节'],
    gallery: [{ title: '蓝调时刻', caption: '水面留住最后一束光。', tone: 'sky' }, { title: '窗边笔记', caption: '港湾上方的一间房。', tone: 'green' }],
  },
  {
    city: 'Tokyo', country: '日本', coordinates: '35.6762° N, 139.6503° E', date: '11.2024',
    note: '无数细小系统，以精确又有人情味的节奏运转。', mood: '电流 / 精密', track: 'Nujabes — Aruarian Dance', color: '#f09a58', region: '亚洲', mapPosition: { x: 80, y: 49 },
    story: '东京在速度里为仪式感留出位置：该站在哪一扇门旁、没有空座的咖啡吧台、路口清空后才响起的那一段歌。',
    highlights: ['首班车前的涩谷', '喫茶店手账页', '一只完美的蜜瓜包'],
    gallery: [{ title: '路口信号', caption: '所有方向同时开始。', tone: 'sunset' }, { title: '安静楼层', caption: '纸门背后的城市。', tone: 'sky' }],
  },
  {
    city: 'Paris', country: '法国', coordinates: '48.8566° N, 2.3522° E', date: '09.2024',
    note: '最好的路线，往往是忘记目的地的那一条。', mood: '石材 / 柔金', track: 'Air — La Femme d’Argent', color: '#e7ad68', region: '欧洲', mapPosition: { x: 39, y: 48 },
    story: '第十一区的一个傍晚，变成了一整夜的步行。城市不断给出新的转角、新的椅子、新的理由，让人推迟搭上最后一班地铁。',
    highlights: ['运河边的速写本', '黄昏的面包店', '11 号地铁线'],
    gallery: [{ title: '长桌晚餐', caption: '晚餐自己决定时间表。', tone: 'sunset' }, { title: '石墙阴影', caption: '一座庭院留住热度。', tone: 'green' }],
  },
  {
    city: 'Reykjavík', country: '冰岛', coordinates: '64.1466° N, 21.9426° W', date: '08.2024',
    note: '风让地图变得没那么确定，而这正是重点。', mood: '火山 / 开阔空气', track: 'Ólafur Arnalds — Near Light', color: '#76a883', region: '北欧', mapPosition: { x: 19, y: 20 },
    story: '那里没有什么能静止太久，天气尤其如此。远处的一条路、低低的地平线，以及足够把每个计划重新排成更好版本的风。',
    highlights: ['正午的黑沙滩', '温泉蒸汽', '一条没有终点的路'],
    gallery: [{ title: '天气转向', caption: '云层换了一种形状。', tone: 'green' }, { title: '远处原野', caption: '让空间自己说话。', tone: 'sky' }],
  },
  {
    city: 'Shanghai', country: '中国', coordinates: '31.2304° N, 121.4737° E', date: '02.2024',
    note: '每次江面转弯，城市就换一种频率。', mood: '雨后 / 脉冲', track: '王菲 — 梦中人', color: '#8bcfe4', region: '亚洲', mapPosition: { x: 73, y: 59 },
    story: '雨让所有表面都有了倒影。在江边和最细小的街道之间，熟悉的地方看起来像一段尚未完成的未来记忆。',
    highlights: ['暴雨后的外滩', '唱片店里的停顿', '玻璃上的江面灯光'],
    gallery: [{ title: '湿润混凝土', caption: '雨把城市重新描了一遍。', tone: 'sky' }, { title: '夜晚水果', caption: '街角最后一只橙子。', tone: 'sunset' }],
  },
  {
    city: 'Barcelona', country: '西班牙', coordinates: '41.3874° N, 2.1686° E', date: '06.2023',
    note: '这里的午后，在时钟说该结束之后仍会继续。', mood: '海盐 / 暖影', track: 'ROSALÍA — HENTAI', color: '#d79562', region: '欧洲', mapPosition: { x: 45, y: 56 },
    story: '城市不断把阳光、瓷砖和海风折进同一个小时。每个街区都像被精心构图，但最好的瞬间总不在任何攻略的时间表里。',
    highlights: ['清晨市场的颜色', '蒙锥克山的空气', '海边的深夜谈话'],
    gallery: [{ title: '瓷砖节奏', caption: '一张有自己天气的网格。', tone: 'sunset' }, { title: '海平线', caption: '一种蓝色遇见更长的蓝色。', tone: 'sky' }],
  },
];

export const nextStop: NextStop = {
  city: 'Lisbon', country: '葡萄牙', coordinates: '38.7223° N, 9.1393° W', window: '2026 / 秋季',
  reason: '想沿着黄色电车一直走，直到城市变成大西洋的地平线。',
};

export const projects: Project[] = [
  { id: 'morning-atlas', title: 'Morning Atlas', category: '网页体验', year: '2026', status: '上线概念', role: '创意方向 · 前端系统', accent: '#69bfe3', summary: '把旅行、音乐与共同游玩整理成一处可漫游的个人信号档案。', outcome: '构建了响应式、数据驱动的单页体验，串联路线、播放和协作互动系统。', tags: ['React', 'TypeScript', '动效', '无障碍 UI'] },
  { id: 'city-rhythm-index', title: 'City Rhythm Index', category: '数据叙事', year: '2025', status: '持续进行', role: '研究 · 信息设计', accent: '#76a883', summary: '一本视觉田野笔记，用来比较城市在交通、天气和日照中的节奏变化。', outcome: '持续生长的一组模块化视觉研究，用清晰对比代替嘈杂仪表盘。', tags: ['数据故事', '地图', '系统设计'] },
  { id: 'signal-room', title: 'Signal Room', category: '创意实验', year: '2025', status: '归档实验', role: '声音概念 · 视觉识别', accent: '#f09a58', summary: '把短篇虚构曲目与地点、质地和被记住的光线配对的一段聆听仪式。', outcome: '一组不依赖外部媒体的封面研究与响应式播放界面实验。', tags: ['声音', '艺术指导', '原型'] },
  { id: 'lantern-bridge', title: 'Lantern Bridge', category: '创意实验', year: '2024', status: '上线概念', role: '交互概念 · 叙事系统', accent: '#d79562', summary: '一个围绕非对称视角和共同前行路线打造的原创协作解谜世界。', outcome: '以轻量浏览器交互演示成对选择、同步状态与可收集记忆。', tags: ['游戏 UX', '叙事', '交互'] },
];

export const contactProfile: ContactProfile = {
  email: 'hello@morningatlas.studio', availability: '正在寻找有趣而真诚的合作', timezone: '上海 / UTC+8',
  channels: [{ label: '邮箱', value: 'hello@morningatlas.studio', href: 'mailto:hello@morningatlas.studio' }, { label: 'GitHub', value: 'github.com/morning-atlas', href: 'https://github.com/morning-atlas' }, { label: '时区', value: '上海 / UTC+8' }],
};

export const tracks: Track[] = [
  { id: 'night-transit', title: 'Night Transit', artist: 'Mira Vale · 演示信号', duration: '04:17', durationSeconds: 257, mood: '末班列车 / 钠灯', category: '通勤', accent: '#f6a5cd', story: '车窗不断借走城市的颜色，一段缓慢离开的信号。回家的路线需要更长结尾时，按下播放。', tags: ['夜深以后', '城市轨道', '柔和脉冲'], visualizer: [28, 61, 43, 87, 52, 76, 35, 92, 46, 67, 83, 38, 59, 72, 31, 88, 50, 65] },
  { id: 'coastline-memory', title: 'Coastline Memory', artist: 'Arden Field · 演示信号', duration: '03:42', durationSeconds: 222, mood: '海盐空气 / 开着的窗', category: '风景', accent: '#9ed5e7', story: '适合火车座位、渡轮甲板，以及地图突然不如窗外天气重要的那一刻。', tags: ['海蓝', '慢旅行', '日光'], visualizer: [46, 72, 35, 66, 88, 43, 57, 79, 31, 61, 91, 48, 74, 39, 83, 54, 69, 42] },
  { id: 'neon-weather', title: 'Neon Weather', artist: 'Kira Bloom · 演示信号', duration: '03:18', durationSeconds: 198, mood: '雨玻璃 / 紫色信号', category: '信号', accent: '#b6c0ff', story: '由倒映的招牌和鼓机组成的一场小风暴，属于每个方向都仍然可能的十字路口。', tags: ['夜行', '电流', '雨天'], visualizer: [73, 42, 84, 57, 91, 36, 68, 88, 49, 77, 32, 95, 54, 71, 44, 82, 61, 39] },
  { id: 'shared-spark', title: 'Shared Spark', artist: 'Lumen Pair · 演示信号', duration: '04:05', durationSeconds: 245, mood: '两只手 / 同一节拍', category: '协作', accent: '#f4d078', story: '为两条分开的路线找到同一节拍的瞬间而写，也适合一起解开下一间不可能房间时播放。', tags: ['协作', '温暖齿轮', '向前'], visualizer: [41, 86, 55, 78, 37, 94, 63, 48, 84, 58, 75, 34, 90, 51, 69, 43, 81, 60] },
  { id: 'first-light-index', title: 'First Light Index', artist: 'Oren Park · 演示信号', duration: '02:56', durationSeconds: 176, mood: '蓝调时刻 / 重启', category: '风景', accent: '#a6c99f', story: '适合拉开窗帘、整理照片，也给下一段目的地留出足够空间的一小段序列。', tags: ['清晨', '绿色房间', '清澈空气'], visualizer: [32, 51, 76, 45, 63, 84, 38, 69, 57, 89, 41, 72, 53, 80, 35, 65, 47, 78] },
];

export const featuredTrack = tracks[0];
export const visualizerHeights = featuredTrack.visualizer;

export const chapters: GameChapter[] = [
  { id: 'clockwork-garden', index: '01', title: '钟摆花园', realm: '常青机械', objective: '把断开的两个季节调回同一个春天。', intro: '花园停在盛放与霜冻之间。Spark 能唤醒根系，Echo 能回应隐藏的铃。', paths: [{ id: 'spark', tone: 'amber', label: '玩家一 / Spark', title: '守住节拍。', copy: '根系记得温暖的脉冲，但只有正确的齿轮先转动才会苏醒。', choices: [{ id: 'turn-sunwheel', label: '转动日轮', detail: '唤醒黄铜根系。' }, { id: 'wake-seedlings', label: '唤醒幼苗', detail: '呼唤细小叶片。' }, { id: 'trace-warmth', label: '追寻暖意', detail: '沿着金色线索走。' }] }, { id: 'echo', tone: 'teal', label: '玩家二 / Echo', title: '找到回应。', copy: '霜铃从另一个季节传回声音，它的回响决定什么能够绽放。', choices: [{ id: 'ring-frostbell', label: '敲响霜铃', detail: '送出回应的音色。' }, { id: 'open-dewgate', label: '打开露门', detail: '放出清晨空气。' }, { id: 'follow-shadow', label: '追随阴影', detail: '读懂沉睡藤蔓。' }] }], solution: { spark: 'turn-sunwheel', echo: 'ring-frostbell' }, relic: { id: 'wind-key', name: '风之钥', description: '一把小小的黄铜钥匙，只有两只手同时转动才能打开门。' } },
  { id: 'echo-city', index: '02', title: '回声之城', realm: '镜像街道', objective: '穿过只会成对回应的街道，送出一段信号。', intro: '黄昏时，城市把路线折成倒影。一位玩家阅读灯光，另一位负责把回应送回去。', paths: [{ id: 'spark', tone: 'amber', label: '玩家一 / Spark', title: '点亮路线。', copy: '一段灯笼序列会画出穿城路径，只需一次小心的脉冲。', choices: [{ id: 'light-arch', label: '点亮拱门', detail: '标记高处的路口。' }, { id: 'wake-tram', label: '唤醒电车', detail: '送出滚动的信号。' }, { id: 'tap-copper', label: '轻敲铜轨', detail: '传递一小段电流。' }] }, { id: 'echo', tone: 'teal', label: '玩家二 / Echo', title: '带回回应。', copy: '镜像城市听不见语言，它只追随在正确时刻返回的形状。', choices: [{ id: 'fold-map', label: '折起地图', detail: '对齐镜像街区。' }, { id: 'answer-arch', label: '回应拱门', detail: '送回灯笼脉冲。' }, { id: 'release-kite', label: '放出风筝', detail: '把消息带到屋顶之上。' }] }], solution: { spark: 'light-arch', echo: 'answer-arch' }, relic: { id: 'lantern-gear', name: '灯笼齿轮', description: '一枚温暖的齿轮，当它的伙伴靠近时会变得更亮。' } },
  { id: 'starlight-workshop', index: '03', title: '星光工坊', realm: '纸质星座', objective: '用分开的记忆，搭起一座通向前方的桥。', intro: '工坊把失落旅程的碎片收在纸星里。两段记忆必须一起安放，才能拼出向前的道路。', paths: [{ id: 'spark', tone: 'amber', label: '玩家一 / Spark', title: '放下第一段桥。', copy: '选出那段即使天空变了，仍能承受重量的记忆。', choices: [{ id: 'place-sunthread', label: '放下日光线', detail: '拉起第一根明亮的线。' }, { id: 'wind-crank', label: '上紧摇柄', detail: '升起纸桥。' }, { id: 'sort-tickets', label: '整理车票', detail: '在旧旅程里找路线。' }] }, { id: 'echo', tone: 'teal', label: '玩家二 / Echo', title: '完成跨越。', copy: '只有第二段记忆向着同一个地平线弯折，桥才会稳稳落下。', choices: [{ id: 'catch-starlight', label: '接住星光', detail: '让桥固定下来。' }, { id: 'place-moonfold', label: '放下月折', detail: '给道路一个弧度。' }, { id: 'read-postmark', label: '读出邮戳', detail: '找回被遗忘的日期。' }] }], solution: { spark: 'place-sunthread', echo: 'catch-starlight' }, relic: { id: 'paper-star', name: '纸星', description: '一枚折叠的星座，指向下一段共同抵达的地平线。' } },
];
