export const PLATFORMS = {
  twitter: {
    name: 'Twitter / X',
    color: '#1DA1F2',
    bgClass: 'bg-[#1DA1F2]',
    textClass: 'text-[#1DA1F2]',
    borderClass: 'border-[#1DA1F2]',
  },
  reddit: {
    name: 'Reddit',
    color: '#FF4500',
    bgClass: 'bg-[#FF4500]',
    textClass: 'text-[#FF4500]',
    borderClass: 'border-[#FF4500]',
  },
  instagram: {
    name: 'Instagram',
    color: '#E1306C',
    bgClass: 'bg-[#E1306C]',
    textClass: 'text-[#E1306C]',
    borderClass: 'border-[#E1306C]',
  },
  tiktok: {
    name: 'TikTok',
    color: '#000000',
    bgClass: 'bg-[#000000]',
    textClass: 'text-[#000000]',
    borderClass: 'border-[#000000]',
  },
  youtube: {
    name: 'YouTube',
    color: '#FF0000',
    bgClass: 'bg-[#FF0000]',
    textClass: 'text-[#FF0000]',
    borderClass: 'border-[#FF0000]',
  },
  facebook: {
    name: 'Facebook',
    color: '#1877F2',
    bgClass: 'bg-[#1877F2]',
    textClass: 'text-[#1877F2]',
    borderClass: 'border-[#1877F2]',
  },
  pinterest: {
    name: 'Pinterest',
    color: '#E60023',
    bgClass: 'bg-[#E60023]',
    textClass: 'text-[#E60023]',
    borderClass: 'border-[#E60023]',
  },
} as const

export type PlatformKey = keyof typeof PLATFORMS

export const PLATFORM_KEYS: PlatformKey[] = [
  'twitter',
  'reddit',
  'instagram',
  'tiktok',
  'youtube',
  'facebook',
]

export const CHART_COLORS = [
  '#20808D',
  '#A84B2F',
  '#1B474D',
  '#BCE2E7',
  '#944454',
  '#FFC553',
]

export const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'most_engaged', label: 'Most Engaged' },
] as const

export const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: 'LayoutDashboard' },
  { href: '/projects', label: 'Projects', icon: 'FolderOpen' },
  { href: '/settings', label: 'Settings', icon: 'Settings' },
] as const
