import { Link } from 'react-router'
import { Pill } from '../ui/Pill'
import { duration, photoUrl } from '../../lib/recipes'
import type { RecipeSummary } from '../../lib/recipeTypes'

/** The photo, or the title's first letter on a dark tile when there is none (mockup, approved). */
export function RecipePhoto({ recipe, className }: { recipe: RecipeSummary; className: string }) {
  if (!recipe.photo) {
    return (
      <span aria-hidden="true" className={`grid place-items-center bg-raised text-page font-semibold text-accent-fg ${className}`}>
        {recipe.title.trim().charAt(0).toUpperCase()}
      </span>
    )
  }
  return (
    <img
      src={photoUrl(recipe, 'thumb')}
      srcSet={`${photoUrl(recipe, 'thumb')} 240w, ${photoUrl(recipe, 'lead')} 900w`}
      sizes="(min-width: 1024px) 320px, 88px"
      alt=""
      loading="lazy"
      className={`bg-raised object-cover ${className}`}
    />
  )
}

/** Prep in violet and cook in amber, as the phases are. */
export function RecipeTimes({ recipe }: { recipe: RecipeSummary }) {
  const { prep_min: prep, cook_min: cook } = recipe.times
  if (!prep && !cook) return null
  return (
    <span className="flex flex-wrap gap-x-2.5 text-caption">
      {!!prep && <span className="text-accent-fg">{duration(prep)} prep</span>}
      {!!cook && <span className="text-cook">{duration(cook)} cook</span>}
    </span>
  )
}

/** A recipe in the list: a row with a square photo on the phone, a card with the photo on top wider up. */
export function RecipeCard({ recipe }: { recipe: RecipeSummary }) {
  return (
    <Link
      to={`/recipes/${encodeURIComponent(recipe.id)}`}
      viewTransition
      className="pressable grid h-full grid-cols-[88px_minmax(0,1fr)] items-center gap-3.5 overflow-hidden rounded-[16px] border border-line-soft bg-card p-2 hover:border-line lg:flex lg:flex-col lg:items-stretch lg:gap-0 lg:p-0"
    >
      <RecipePhoto recipe={recipe} className="size-[88px] rounded-[11px] lg:h-40 lg:w-full lg:rounded-none" />
      <span className="flex min-w-0 flex-col gap-1 lg:px-3.5 lg:pt-3 lg:pb-3.5">
        <span className="text-title leading-snug font-semibold">{recipe.title}</span>
        <RecipeTimes recipe={recipe} />
        {(recipe.needs_review || recipe.tags.length > 0) && (
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-faint">
            {recipe.needs_review && <Pill tone="warn">Needs review</Pill>}
            {recipe.tags.slice(0, 4).map((tag) => (
              <span key={tag}>#{tag}</span>
            ))}
          </span>
        )}
      </span>
    </Link>
  )
}
