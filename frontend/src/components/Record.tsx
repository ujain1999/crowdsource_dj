interface Props {
  art?: string | null
  spinning: boolean
  blankLabel?: string
  className?: string
}

/** ytimg thumbnails are 4:3 with black bars; they get zoomed to hide them. */
export const isLetterboxed = (url?: string | null) => !!url && url.includes('i.ytimg.com')

export default function Record({ art, spinning, blankLabel = 'CDJ', className = '' }: Props) {
  return (
    <div className={`record ${spinning ? 'is-spinning' : ''} ${className}`} aria-hidden="true">
      <div className="record-shine" />
      <div className="record-label">
        {art ? (
          <img referrerPolicy="no-referrer" src={art} alt="" className={isLetterboxed(art) ? 'is-letterboxed' : ''} />
        ) : (
          blankLabel && <div className="record-label-blank">{blankLabel}</div>
        )}
      </div>
      <div className="record-hole" />
    </div>
  )
}
