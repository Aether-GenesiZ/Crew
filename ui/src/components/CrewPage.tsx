import { useEffect, useState } from 'react'
import * as sdk from '@hermes/plugin-sdk'
import { useTheme } from '@hermes/plugin-sdk'
import type { CrewApi } from '../api'
import { crewVarsFromTheme } from '../theme'
import { cardFromHash, boardFromQuery } from '../open-card'
import { setCardPageOpen } from '../card-open'
import { store } from './boardUtil'
import type { Route } from '../route'
import { Board } from './Board'
import { CardPage } from './CardPage'
import { Splash } from './Splash'

let splashShown = false

// Desktop page root (fills its route area whatever the parent is: a sized block, or a flex row or column; the splash
// overlay is absolute inset:0 on it): puts the host theme on the --crew-* variables, then the shared board or card page. Navigation is
// state (Desktop owns the address bar): a tile opens its card, the card's back button returns to the board.
export function CrewPage({ api }: { api: CrewApi }) {
  const { theme, renderedMode } = useTheme()
  const [route, setRoute] = useState<Route>(() => ({ page: 'board', all: false }))
  // The board this page shows. A link from outside ("#/crew?card=<id>[&board=<slug>]": the blocked-card
  // toast, a kanban-graph jump) sets it; the switcher's pick persists across the page's remounts
  // (Desktop unmounts /crew when you leave it). '' = the active board.
  const [boardSlug, setBoardSlug] = useState<string>(() => boardFromQuery(window.location.hash) || store('page.board') || '')
  useEffect(() => {
    const go = () => {
      const id = cardFromHash(window.location.hash)
      const slug = boardFromQuery(window.location.hash)
      if (slug) setBoardSlug(slug)
      if (id) setRoute({ page: 'card', id })
    }
    go()
    window.addEventListener('hashchange', go)
    return () => window.removeEventListener('hashchange', go)
  }, [])
  const pickBoard = (slug: string) => { setBoardSlug(slug); store('page.board', slug || null) }
  const back = () => setRoute({ page: 'board', all: false })
  // The card page's cross-link into the kanban graph: only where the shell brings a navigator
  // (Desktop does; the served page and the dashboard tab draw nothing). The graph's deep link is
  // `#/kanban-graph?task=<board>/<id>` - the same door its own notifications use.
  const host = sdk.host
  const navigator = typeof host?.navigate === 'function' ? (board: string, id: string) =>
    host.navigate!('/kanban-graph?task=' + encodeURIComponent(board + '/' + id)) : undefined
  const openSession = host?.openSession
  const openChat = typeof openSession === 'function'
    ? (profile: string, session: string) => { void openSession.call(host, session, { profile }) }
    : undefined
  // Once per app session: the flag lives in this module, so it survives the page remounting on every route change
  // (Desktop unmounts /crew when you leave it) and resets when the app restarts. It is set in an effect, not in the
  // initializer, so a double-invoked initializer cannot swallow the splash.
  const [splash] = useState(() => !splashShown)
  useEffect(() => { splashShown = true }, [])
  const card = route.page === 'card'
  // the flow pane steps aside while the card page shows the full flow; leaving /crew unmounts this, which clears it
  useEffect(() => { setCardPageOpen(card); return () => setCardPageOpen(false) }, [card])
  return (
    <div
      className="crew-scope"
      style={{ ...crewVarsFromTheme(theme, renderedMode), background: 'var(--crew-bg)', color: 'var(--crew-fg)', height: '100%', minHeight: '100%', width: '100%', minWidth: 0, flex: '1 1 auto', alignSelf: 'stretch', boxSizing: 'border-box', position: 'relative', overflow: card ? 'hidden' : 'auto' }}
    >
      {splash ? <Splash api={api} /> : null}
      {route.page === 'card'
        ? <CardPage api={api} id={route.id} onBack={back} openChat={openChat} board={boardSlug} onGraph={navigator} />
        : <Board api={api} onOpenCard={id => setRoute({ page: 'card', id })} boardSlug={boardSlug} onBoard={pickBoard} home={back} />}
    </div>
  )
}
