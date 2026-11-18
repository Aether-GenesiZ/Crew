import { boardFromQuery, cardFromSearch } from './open-card'
import { boardParam, withBoard } from './components/boardUtil'

// The browser shell's routes, by location.pathname: "/" is the board (?all=1 shows every lane, ?older=1 the older done
// cards), "/card/<id>" or "/crew?card=<id>" (the link crew sends out) a card. `board` (from ?board=<slug>) is the
// switcher's pick: '' = the active board; another slug serves that board without moving the active one.
export type Route = { page: 'board'; all: boolean; older?: boolean; board?: string } | { page: 'card'; id: string; board?: string }

export function parseLocation(pathname: string, search: string): Route {
  const board = boardFromQuery('/crew?' + (search || '').replace(/^\?/, ''))
  const m = /^\/card\/([A-Za-z0-9_-]+)\/?$/.exec(pathname)
  if (m) return { page: 'card', id: m[1], board }
  if (/^\/crew\/?$/.test(pathname)) {
    const id = cardFromSearch(search)
    if (id) return { page: 'card', id, board }
  }
  return { page: 'board', all: /[?&]all=1/.test(search), ...(/[?&]older=1/.test(search) ? { older: true } : {}), board }
}
export function hrefFor(r: Route): string {
  if (r.page === 'card') return withBoard('/card/' + r.id, r.board)
  const q = [r.all ? 'all=1' : '', r.older ? 'older=1' : '', boardParam(r.board)].filter(Boolean).join('&')
  return q ? '/?' + q : '/'
}
