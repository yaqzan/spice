// The step body, read the way it is cooked.
//
// A step is prose, and prose read over a hot pan is a wall. Three things in it
// are worth finding without reading: what goes in, how much of it, and how long.
// So the body is walked once and those three are lifted out of the sentence
// without moving them — an ingredient becomes a stamp carrying its own
// measurement, a bowl reference becomes a chip that matches the reminder
// underneath, and a duration is set in bold. Everything else stays exactly as
// the model wrote it.
//
// Nothing here knows a spice name. The stamps are built from what the payload
// already says about THIS step, which is the same rule the rest of the app
// follows: no second registry in TypeScript (see CLAUDE.md).

import type { ReactNode } from 'react'
import { Amount } from './Amount'

/** One thing the sentence may name, and what the stamp shows beside it. */
export type Stamp = {
  /** The ingredient's own name, as the payload spells it. */
  label: string
  /** How much of it. Blank is allowed; the stamp then just carries the dot. */
  amount: string
  /** A jar's colour. Absent for anything that came out of the fridge. */
  color?: string
}

/** Head words too generic to identify an ingredient on their own.
 *
 *  "add a splash of water" and "1 1/2 cups water for rice" are different water.
 *  Stamping the first with the second's measurement would be a confident lie, so
 *  a bare match on one of these is left as plain text. The full phrase still
 *  matches — this only rules out the shortened form. */
const VAGUE = new Set(['water', 'stock', 'broth', 'powder', 'seasoning', 'blend',
                       'mix', 'salt', 'pepper', 'sauce', 'paste', 'seeds', 'seed',
                       'leaves', 'flakes', 'pieces'])

const BOWL = /BOWL\s*\d+/
// Durations, however they are written: "45 minutes", "6-8 minutes", "30 seconds",
// "1 1/2 hours". The number is bold along with its unit, because a bare bold
// numeral in a sentence full of numbers is noise.
const TIME = /\b\d+(?:\s+\d+\/\d+|[./]\d+)?(?:\s*[-–—]\s*\d+(?:[./]\d+)?)?\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?)\b|\bovernight\b/
const IS_TIME = /(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|overnight)$/i

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** The ways a sentence might refer to one ingredient.
 *
 *  A payload says "unsalted butter" and "yellow onion"; a step says "the butter"
 *  and "the onion". So the head noun counts as the same thing — but only the
 *  head, and only when it is not one of the vague ones above. The first word is
 *  kept with it too ("fresh hot chile" -> "fresh chile"), because a stamp that
 *  starts one word late leaves an orphan adjective outside the box. */
function phrasesFor(label: string): string[] {
  // A jar's parenthetical is a gloss, not part of what a sentence calls it:
  // "Silk Chili (Aleppo)" is written as Silk Chili in a step.
  const clean = label.replace(/\([^)]*\)/g, ' ').trim().replace(/\s+/g, ' ')
  if (!clean) return []
  const words = clean.split(' ')
  const head = words[words.length - 1]
  const vague = VAGUE.has(head.toLowerCase().replace(/[^a-z]/g, ''))
  // A shopping line called simply "Water" is as unresolvable as the head noun
  // of "water for rice" — and the recipe that listed both had a step reading
  // "bring the rice water to a boil", which stamped the beef's half cup onto it.
  if (words.length === 1) return vague ? [] : [clean]
  const out = [clean, words.slice(-2).join(' ')]
  if (words.length > 2) out.push(`${words[0]} ${head}`)
  if (!vague) out.push(head)
  return out.filter((p) => p.length >= 3 && /^[\w][\w\s'-]*$/.test(p))
}

/** The measurement, without the handling note trailing it.
 *
 *  A shopping list can afford "1 red serrano or small red jalapeño, finely
 *  chopped"; a stamp sitting inside a sentence cannot — it stops being a chip
 *  and becomes a second sentence. The clause before the first comma is the part
 *  a cook needs at that moment; the rest is still on the shopping list. */
function shortAmount(amount: string): string {
  let first = (amount || '').split(/[,;(]/)[0].trim()
  // "1 red serrano or small red jalapeño" is a choice, not a measurement. The
  // first option is enough to reach for; the shopping list still offers both.
  if (first.length > 16) first = first.split(/\s+or\s+/)[0].trim()
  return first || amount || ''
}

// A measurement written into the sentence: "3/4 TEAsp", "1 TBsp", "4 cloves",
// "1 1/2 cups", "a pinch". Every one of them gets the same chip, whether or not
// an ingredient name happens to sit beside it — a step that stamps one of its
// three amounts and leaves the other two as bare text looks broken, and the two
// it skipped are the ones the eye then misses.
const UNIT = 'TEAsp|TBsp|tsp|tbsp|cups?|cloves?|slices?|sprigs?|lbs?|pounds?|oz|ounces?|inch|cm'
const MEASURE = new RegExp(
  `\\b\\d+(?:\\s+\\d+/\\d+|[./]\\d+)?(?:\\s*(?:to|[-–—])\\s*\\d+(?:[./]\\d+)?)?[\\s-]*(?:${UNIT})\\b`
  + '|\\ba pinch\\b', 'i')

/** Spoons, cups, counts and weights are different kinds of thing.
 *
 *  Used to decide whether a number beside an ingredient is that ingredient's
 *  number. "1/4 TEAsp rice salt" puts a spoon next to the word rice, which is
 *  measured in cups — the spoon belongs to the salt further along the sentence,
 *  and merging it into a rice stamp would invent a quarter-teaspoon of rice. */
function unitClass(text: string): string {
  const found = /(TEAsp|TBsp|tsp|tbsp|cups?|cloves?|slices?|sprigs?|lbs?|pounds?|oz|ounces?|inch|cm|pinch)/i
    .exec(text || '')
  if (!found) return ''
  const unit = found[1].toLowerCase().replace(/s$/, '')
  if (/^(teasp|tbsp|tsp|pinch)$/.test(unit)) return 'spoon'
  if (unit === 'cup') return 'cup'
  if (/^(lb|pound|oz|ounce)$/.test(unit)) return 'weight'
  if (/^(inch|cm)$/.test(unit)) return 'length'
  return 'count'
}

type Token =
  | { kind: 'text'; text: string }
  | { kind: 'time'; text: string }
  | { kind: 'measure'; text: string }
  | { kind: 'bowl'; text: string; bowl: number }
  /** `own` is a measurement lifted out of the sentence, which wins over the
   *  shopping list's — that holds the whole recipe's worth ("2 TBsp, divided")
   *  and printing it beside a step that wants half is a contradiction standing
   *  next to a hot pan. It reads ahead of the name, as the sentence wrote it. */
  | { kind: 'stamp'; text: string; index: number; own?: string }

/** Walk a body once and mark up what can be marked up.
 *
 *  Exported because the card needs to know which ingredients a step actually
 *  names before it decides which step gets to carry each measurement. */
export function scan(text: string, stamps: Stamp[]): Token[] {
  const body = text || ''
  // A phrase claimed by two different ingredients is dropped rather than guessed
  // at: with both "water for rice" and "water or beef stock" on the list, a bare
  // "water" cannot be resolved, and picking one would put the wrong measurement
  // in the cook's hand.
  const owners = new Map<string, number>()
  stamps.forEach((stamp, index) => {
    for (const phrase of phrasesFor(stamp.label)) {
      const key = phrase.toLowerCase()
      if (owners.has(key) && owners.get(key) !== index) owners.set(key, -1)
      else if (!owners.has(key)) owners.set(key, index)
    }
  })
  const phrases = [...owners.entries()]
    .filter(([, index]) => index >= 0)
    .map(([phrase]) => phrase)
    // Longest first, so "tomato paste" is not eaten by "tomato".
    .sort((a, b) => b.length - a.length)
    .map(escape)
  // Times before measurements, so "6-8 minutes" is a duration rather than a
  // number with a stray unit; measurements before names, so the amount is in
  // hand by the time the ingredient beside it is decided.
  const parts = [BOWL.source, TIME.source, MEASURE.source]
  if (phrases.length) parts.push(`\\b(?:${phrases.join('|')})\\b`)
  const pattern = new RegExp(`(${parts.join('|')})`, 'gi')

  const tokens: Token[] = []
  let last = 0
  for (const match of body.matchAll(pattern)) {
    const found = match[0]
    const at = match.index ?? 0
    if (at > last) tokens.push({ kind: 'text', text: body.slice(last, at) })
    last = at + found.length

    const bowl = /^bowl\s*(\d+)$/i.exec(found)
    if (bowl) {
      tokens.push({ kind: 'bowl', text: found, bowl: Number(bowl[1]) })
      continue
    }
    const index = owners.get(found.toLowerCase())
    if (index === undefined || index < 0) {
      // Not a bowl and not an ingredient, so it is one of the other two — a
      // duration, or an amount. Anything that is neither goes back into the
      // sentence untouched rather than being shouted for no reason.
      if (IS_TIME.test(found)) tokens.push({ kind: 'time', text: found })
      else if (MEASURE.test(found)) tokens.push({ kind: 'measure', text: found })
      else tokens.push({ kind: 'text', text: found })
      continue
    }
    // Did the sentence already say how much, right here? An amount separated by
    // words ("3/4 TEAsp of the measured salt") stays its own chip: absorbing it
    // would have to swallow the words in between, and rewriting the sentence is
    // not this function's job.
    const previous = tokens[tokens.length - 1]
    const gap = previous?.kind === 'text' && /^\s*$/.test(previous.text)
      ? tokens[tokens.length - 2] : previous
    if (gap?.kind === 'measure') {
      const mine = unitClass(stamps[index].amount)
      const theirs = unitClass(gap.text)
      if (!mine || !theirs || mine === theirs) {
        // The sentence's own number, folded into the stamp.
        tokens.splice(tokens.indexOf(gap), 1)
        tokens.push({ kind: 'stamp', text: found, index, own: gap.text.trim() })
      } else {
        // A spoon standing next to something measured in cups is not that
        // thing's amount — it belongs further along the sentence. Leave the name
        // as plain words rather than pinning the wrong number to it.
        tokens.push({ kind: 'text', text: found })
      }
      continue
    }
    tokens.push({ kind: 'stamp', text: found, index })
  }
  if (last < body.length) tokens.push({ kind: 'text', text: body.slice(last) })
  return tokens
}

/** Which stamps this body names at all. */
export function mentioned(text: string, stamps: Stamp[]): Set<number> {
  const out = new Set<number>()
  for (const token of scan(text, stamps)) {
    if (token.kind === 'stamp') out.add(token.index)
  }
  return out
}

type Props = {
  text: string
  stamps: Stamp[]
  /** Stamp indices allowed to carry their measurement here. Anything left out
   *  still reads as plain words — the card gives an ingredient its number in
   *  the step that puts it in the pan, and later steps just talk about it. */
  allow?: Set<number>
  /** Bowl numbers that have a reminder underneath, so the chip is honest. */
  bowls?: Set<number>
  /** Corrections for bowl numbers the model wrote from its own counting. */
  renumber?: Map<number, number>
}

export function StepText({ text, stamps, allow, bowls, renumber }: Props) {
  const nodes: ReactNode[] = []
  // One measurement per ingredient per step as well as per recipe: "cook until
  // the onion softens" three clauses after the onion went in is the same onion.
  const stamped = new Set<number>()
  let key = 0
  for (const token of scan(text, stamps)) {
    if (token.kind === 'text') {
      nodes.push(token.text)
    } else if (token.kind === 'time') {
      nodes.push(<b key={key++} className="step-time">{token.text}</b>)
    } else if (token.kind === 'measure') {
      nodes.push(
        <span key={key++} className="stamp stamp-measure">
          <b className="stamp-amount"><Amount>{token.text}</Amount></b>
        </span>)
    } else if (token.kind === 'bowl') {
      const bowl = renumber?.get(token.bowl) ?? token.bowl
      const known = bowls?.has(bowl)
      nodes.push(
        <b key={key++} className={`step-bowl-ref${known ? '' : ' step-bowl-loose'}`}>
          {token.text.replace(/\d+/, String(bowl))}
        </b>)
    } else if (!token.own && ((allow && !allow.has(token.index)) || stamped.has(token.index))) {
      // A step that repeats the ingredient without a number is talking about it,
      // not adding it — but one that gives its own measurement is adding it
      // again, and that is worth a stamp however many came before.
      nodes.push(token.text)
    } else {
      stamped.add(token.index)
      const stamp = stamps[token.index]
      const amount = token.own || shortAmount(stamp.amount)
      const measure = amount && <b className="stamp-amount"><Amount>{amount}</Amount></b>
      nodes.push(
        <span key={key++} className={`stamp${stamp.color ? '' : ' stamp-kitchen'}`}>
          {/* The dot is the jar's own colour, the same one it wears on the rack
              and in its bowl. Anything from the fridge has no jar and therefore
              no colour, and an empty ring in its place reads as a swatch that
              failed to load — so it simply goes without. A dot on a stamp then
              means one thing: this is on the rack, and that is where it is. */}
          {stamp.color && <i style={{ background: stamp.color }} />}
          {/* The sentence's own measurement keeps the sentence's word order:
              "1 TBsp oil", not "oil 1 TBsp". */}
          {token.own && measure}
          <span className="stamp-name">{token.text}</span>
          {!token.own && measure}
        </span>)
    }
  }
  return <>{nodes}</>
}
