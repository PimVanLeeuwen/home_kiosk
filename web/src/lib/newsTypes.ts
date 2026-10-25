/** Shapes of the News, Saved and feed settings endpoints (collector app/news). */

export interface NewsGroup {
  id: string
  title: string
  unread: number
}

export interface Article {
  id: string
  url: string
  title: string
  source: string
  group_id: string
  published: string
  read: boolean
}

export interface ArticleList {
  articles: Article[]
  total: number
}

/** Plain text only: the hub never passes a site's HTML to the browser. */
export interface Block {
  type: 'heading' | 'paragraph' | 'quote' | 'list' | 'image'
  text: string
  items: string[]
  /** For images: the hub's own proxy path. */
  src: string
}

export interface ArticleContent {
  ok: boolean
  /** Why there is nothing to read here, when not ok. */
  reason: string | null
  title: string | null
  author: string | null
  date: string | null
  site: string | null
  blocks: Block[]
}

export interface Bookmark {
  id: string
  url: string
  title: string
  site: string | null
  created: string | null
  published: string | null
  description: string | null
  reading_minutes: number | null
  progress: number
  archived: boolean
  /** False while Readeck is still fetching the page, or when that failed. */
  readable: boolean
  thumbnail: boolean
}

export interface BookmarkList {
  bookmarks: Bookmark[]
  total: number
}

export interface Feed {
  id: number
  group_id: string
  url: string
  name: string | null
  checked_at: string | null
  item_count: number | null
  error: string | null
}

export interface FeedGroup {
  id: string
  title: string
  feeds: Feed[]
}

/** The newest story of each group, the lead first (/api/news/headlines). */
export interface Headline {
  id: string
  group_id: string
  group: string
  title: string
  source: string
  url: string
  published: string
  summary: string | null
  /** Stored pictures: "lead" has both sizes, "thumb" only the square. */
  image: 'lead' | 'thumb' | null
  /** A grouped story (M26): Claude's one sentence, and the other feeds' articles on it. */
  story?: string | null
  sources?: { id: string; source: string; url: string }[]
}

export interface HeadlinesResponse {
  as_of: string
  stale: boolean
  items: Headline[]
  /** Top stories by event, grouped by Claude; otherwise the newest of each group. */
  grouped?: boolean
}
