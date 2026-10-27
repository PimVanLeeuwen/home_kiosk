import { ArrowLeft, Camera, ClipboardPaste, Copy, Trash2, Undo2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { PageHeader } from '../components/PageHeader'
import { ActionMenu } from '../components/recipes/ActionMenu'
import { PasteDialog } from '../components/recipes/PasteDialog'
import { Facts, IngredientLists, Phases } from '../components/recipes/RecipeParts'
import { Button } from '../components/ui/Button'
import { Surface } from '../components/ui/Card'
import { Loading, PageUnavailable } from '../components/ui/states'
import { ApiError, getJson, sendJson } from '../lib/api'
import { copyText } from '../lib/clipboard'
import { cn } from '../lib/cn'
import { formatAgo } from '../lib/format'
import { photoData } from '../lib/photoData'
import { photoUrl } from '../lib/recipes'
import type { RecipeDetail } from '../lib/recipeTypes'
import { useApi } from '../lib/useApi'

/** What Copy with prompt puts above a recipe from Tandoor, after the format's guide. */
const REWORK =
  'Rework this recipe into prep and cook phases (every prep phase first), with each ingredient in the step that uses it and its pantry flag. Keep the id and the texts, and leave needs_review out. Answer with the JSON only.'

const hostOf = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

/** One recipe (plan.md M30): what to get and check, then the phases, prep before the heat. */
export function RecipePage() {
  const id = useParams().id ?? ''
  const { data, error, loading, reload } = useApi<RecipeDetail>(`/api/recipes/${encodeURIComponent(id)}`)
  if (loading && !data) return <Loading what="the recipe" />
  if (!data) {
    const missing = error instanceof ApiError && error.status === 404
    return (
      <>
        <BackLink />
        {missing ? (
          <PageUnavailable what="This recipe" detail="It may have been deleted, or its id changed in a paste." />
        ) : (
          <PageUnavailable what="This recipe" detail={error?.message} onRetry={reload} />
        )}
      </>
    )
  }
  // A new version (a paste, an undo) starts again from its own servings.
  return <Recipe key={`${data.recipe.id} ${data.updated_at}`} detail={data} reload={reload} />
}

function BackLink() {
  return (
    <Link to="/recipes" viewTransition className="mb-4 inline-flex items-center gap-1.5 text-small text-muted hover:text-fg">
      <ArrowLeft aria-hidden="true" className="size-4" />
      Recipes
    </Link>
  )
}

function Recipe({ detail, reload }: { detail: RecipeDetail; reload: () => void }) {
  const { recipe } = detail
  const navigate = useNavigate()
  const [servings, setServings] = useState(recipe.servings)
  const [pasting, setPasting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<{ ok: boolean; text: string }>()
  const fileInput = useRef<HTMLInputElement>(null)
  const factor = servings / recipe.servings

  async function act(work: () => Promise<string | void>, failed: string) {
    setBusy(true)
    setNotice(undefined)
    try {
      const done = await work()
      if (done) setNotice({ ok: true, text: done })
    } catch (err) {
      setNotice({ ok: false, text: `${failed}: ${err instanceof Error ? err.message : 'the hub did not answer.'}` })
    } finally {
      setBusy(false)
    }
  }

  const copyJson = () =>
    act(async () => {
      await copyText(JSON.stringify(recipe, null, 2))
      return 'Copied the recipe as JSON, to change it with Claude.'
    }, 'Nothing copied')

  const copyWithPrompt = () =>
    act(async () => {
      const guide = getJson<{ guide: string }>('/api/recipes/schema').then(
        ({ guide: g }) => `${g}\n\n${REWORK}\n\n${JSON.stringify(recipe, null, 2)}`,
      )
      await copyText(guide)
      return 'Copied with the prompt. Paste Claude’s answer back with Paste JSON.'
    }, 'Nothing copied')

  const undo = () =>
    act(async () => {
      await sendJson('POST', `/api/recipes/${encodeURIComponent(recipe.id)}/undo`, {})
      reload()
      return 'Back to the version before the last paste.'
    }, 'Could not undo')

  const remove = () =>
    act(async () => {
      await sendJson('DELETE', `/api/recipes/${encodeURIComponent(recipe.id)}`)
      navigate('/recipes', { state: { notice: `Deleted "${recipe.title}".` }, viewTransition: true })
    }, 'Not deleted')

  const upload = (file: File) =>
    act(async () => {
      await sendJson('PUT', `/api/recipes/${encodeURIComponent(recipe.id)}/photo`, { data: await photoData(file) })
      reload()
      return 'The photo is in.'
    }, 'No new photo')

  const actions = [
    { label: 'Copy JSON', hint: 'The recipe as JSON, to change it with Claude', icon: Copy, onSelect: copyJson },
    { label: 'Paste JSON', hint: 'Replace this recipe with a new version', icon: ClipboardPaste, onSelect: () => setPasting(true) },
    ...(detail.previous_at
      ? [{ label: 'Undo last paste', hint: `Pasted ${formatAgo(detail.previous_at)}; back to the version before`, icon: Undo2, onSelect: undo }]
      : []),
    { label: detail.photo ? 'Change photo' : 'Add photo', hint: 'Take one or pick from the library', icon: Camera, onSelect: () => fileInput.current?.click() },
    { label: 'Delete recipe', hint: 'Asks once more', icon: Trash2, onSelect: () => setConfirming(true), danger: true },
  ]

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <BackLink />
        <div className="mb-4 flex items-center gap-2">
          <span className="hidden md:block">
            <Button onClick={copyJson} disabled={busy}>
              <Copy aria-hidden="true" className="size-4" />
              Copy JSON
            </Button>
          </span>
          <ActionMenu label="Recipe actions" actions={actions} />
        </div>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        aria-label="Photo"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (file) upload(file)
        }}
      />
      <PasteDialog
        open={pasting}
        target={{ id: recipe.id, title: recipe.title }}
        onClose={() => setPasting(false)}
        onSaved={(note) => {
          setPasting(false)
          setNotice({ ok: true, text: note })
          reload()
        }}
      />

      {confirming && (
        <Surface padding="compact" role="alert" className="mb-4 flex flex-wrap items-center gap-3 border-down/40">
          <p className="basis-full sm:basis-0 sm:flex-1">Delete &quot;{recipe.title}&quot; for good? There is no undo.</p>
          <Button variant="danger" onClick={remove} disabled={busy}>
            <Trash2 aria-hidden="true" className="size-4" />
            Delete for good
          </Button>
          <Button onClick={() => setConfirming(false)} disabled={busy}>
            Keep it
          </Button>
        </Surface>
      )}
      {notice && (
        <p role="status" className={cn('mb-4 text-small', notice.ok ? 'text-up' : 'text-down')}>
          {notice.text}
        </p>
      )}

      {/* On the phone: photo, title, facts and ingredients, phases. On a wide screen the photo,
          facts and ingredients are one column on the left, beside the title and the phases. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(300px,360px)_minmax(0,1fr)] lg:grid-rows-[auto_1fr] lg:gap-x-8">
        <div className="contents lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:flex lg:flex-col lg:gap-5">
          {detail.photo && (
            <img
              src={photoUrl({ id: recipe.id, photo: detail.photo }, 'lead')}
              alt=""
              className="order-1 aspect-[3/2] w-full rounded-[16px] border border-line-soft bg-raised object-cover"
            />
          )}
          <div className="order-3 flex flex-col gap-5">
            <Facts recipe={recipe} servings={servings} onServings={setServings} />
            <IngredientLists recipe={recipe} factor={factor} />
          </div>
        </div>
        <div className="order-2 flex flex-col gap-2 lg:col-start-2 lg:row-start-1">
          {recipe.tags.length > 0 && (
            <p className="flex flex-wrap gap-x-2 text-caption text-faint">
              {recipe.tags.map((t) => (
                <span key={t}>#{t}</span>
              ))}
            </p>
          )}
          <PageHeader title={recipe.title} subtitle={recipe.intro ?? undefined} />
          {detail.needs_review && (
            <Surface padding="compact" className="-mt-3 flex flex-col gap-2 border-warn/30 bg-warn/5">
              <p className="font-semibold text-warn">Not in phases yet</p>
              <p className="text-small text-muted">
                This came from Tandoor as one cook phase. Copy it with the prompt for Claude, then paste the reworked version back.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={copyWithPrompt} disabled={busy}>
                  <Copy aria-hidden="true" className="size-4" />
                  Copy with prompt
                </Button>
                <Button size="sm" onClick={() => setPasting(true)}>
                  <ClipboardPaste aria-hidden="true" className="size-4" />
                  Paste JSON
                </Button>
              </div>
            </Surface>
          )}
        </div>
        <div className="order-4 flex flex-col gap-4 lg:col-start-2 lg:row-start-2">
          <Phases recipe={recipe} factor={factor} />
          {recipe.notes && (
            <Surface padding="compact">
              <h2 className="mb-1 text-small font-semibold text-muted">Notes</h2>
              <p className="whitespace-pre-line">{recipe.notes}</p>
            </Surface>
          )}
          {recipe.source && (
            <p className="text-small text-faint">
              Source:{' '}
              <a href={recipe.source} target="_blank" rel="noopener noreferrer" className="text-accent-fg hover:underline">
                {hostOf(recipe.source)}
              </a>
            </p>
          )}
        </div>
      </div>
    </>
  )
}
