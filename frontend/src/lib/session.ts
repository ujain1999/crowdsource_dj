// Per-tab identity. The login token lives in localStorage (so new tabs stay
// logged in) and is mirrored in sessionStorage, so two tabs can be logged in
// as different people.

const TOKEN = 'cdj.token'
const CLIENT = 'cdj.client'
const NAME = 'cdj.guestName'

function read(key: string, storage: Storage): string | null {
  try {
    return storage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null, storage: Storage) {
  try {
    if (value === null) storage.removeItem(key)
    else storage.setItem(key, value)
  } catch {
    /* storage unavailable (private mode); fine */
  }
}

export function getToken(): string | null {
  const own = read(TOKEN, sessionStorage)
  if (own !== null) return own || null // "" means "logged out in this tab"
  return read(TOKEN, localStorage)
}

export function setToken(token: string | null) {
  write(TOKEN, token ?? '', sessionStorage)
  write(TOKEN, token, localStorage)
}

function randomId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, '0')).join('')
}

export function getClientId(): string {
  let id = read(CLIENT, sessionStorage)
  if (!id) {
    id = randomId()
    write(CLIENT, id, sessionStorage)
  }
  return id
}

const ADJECTIVES = [
  'Funky', 'Groovy', 'Sleepy', 'Wobbly', 'Sparkly', 'Bouncy', 'Moody', 'Fizzy', 'Jazzy', 'Snazzy',
  'Dizzy', 'Cosmic', 'Velvet', 'Neon', 'Lo-fi', 'Chunky', 'Breezy', 'Twangy', 'Loud', 'Mellow',
]
const ANIMALS = [
  'Llama', 'Otter', 'Walrus', 'Flamingo', 'Axolotl', 'Pangolin', 'Capybara', 'Narwhal', 'Toucan',
  'Wombat', 'Lobster', 'Moth', 'Yak', 'Gecko', 'Puffin', 'Badger', 'Koala', 'Heron', 'Newt', 'Hedgehog',
]

export function getGuestName(): string {
  let name = read(NAME, sessionStorage)
  if (!name) {
    const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)]
    name = `${pick(ADJECTIVES)} ${pick(ANIMALS)}`
    write(NAME, name, sessionStorage)
  }
  return name
}

export function setGuestName(name: string) {
  write(NAME, name, sessionStorage)
}

export function formatRoomId(raw: string): string {
  const letters = raw.replace(/[^a-z]/gi, '').toUpperCase().slice(0, 12)
  return letters.match(/.{1,4}/g)?.join('-') ?? ''
}

export function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) seconds = 0
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

/** A stable, friendly color for a person, from their key. */
export function colorFor(key: string | null | undefined): string {
  const palette = ['#FF4FA3', '#2F5BEA', '#E8A500', '#18A873', '#9B5DE5', '#F15BB5', '#00A6C8', '#FF7A3D']
  let h = 0
  for (const ch of key ?? '') h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return palette[h % palette.length]
}
