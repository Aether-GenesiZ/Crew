// Opening a card from outside the page (the blocked-card toast): Desktop's router owns the address, so the card id rides
// the route's query, "#/crew?card=<id>". A fresh stamp per link makes a second link to the same card a changed hash, so
// the page sees it again after the owner went back to the board.
import { withBoard } from './components/boardUtil'

export const CREW_ROUTE = '/crew'

export const cardLink = (id: string, stamp: number = Date.now(), board?: string): string =>
  CREW_ROUTE + withBoard('?card=' + encodeURIComponent(id) + '&n=' + stamp, board)

// The card id of a location hash ("#/crew?card=t_x&n=1"), or '' when the hash opens no card.
export function cardFromHash(hash: string): string {
  const m = /^#?\/crew\?(.*)$/.exec(hash || '')
  const id = m ? new URLSearchParams(m[1]).get('card') || '' : ''
  return /^[A-Za-z0-9_-]+$/.test(id) ? id : ''
}

const CARD_ID = /^[A-Za-z0-9_-]+$/
const BOARD_SLUG = /^[a-z0-9][a-z0-9_-]*$/

// The board a hash or query names ("#/crew?card=t_x&board=lts-odoo", or a bare "?board=x"), or '' when
// it names none (the active board). Accepts both shapes: a Desktop hash link ("/crew?..."), a served
// page or dashboard tab search ("?card=...&board=...").
export function boardFromQuery(search: string): string {
  const q = (search || '').replace(/^#?\/crew\??/, '').replace(/^\?/, '')
  const id = new URLSearchParams(q).get('board') || ''
  return BOARD_SLUG.test(id) ? id : ''
}

// The card id in a location query ("?card=t_x"), or '' when the query opens no card: what a shared card link carries
// when it lands on the served page or the hosted Crew tab.
export function cardFromSearch(search: string): string {
  const id = new URLSearchParams((search || '').replace(/^\?/, '')).get('card') || ''
  return CARD_ID.test(id) ? id : ''
}
