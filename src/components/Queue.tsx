import React from 'react'
import './Queue.css'
import { Song } from '../contexts/RoomContext'

interface QueueProps {
  songs: Song[]
  isAdmin: boolean
  currentSong?: Song | null
  onSongClick?: (song: Song) => void
  onReorder?: (songs: Song[]) => void
  onRemove?: (songId: string) => void
}

export default function Queue({ songs, isAdmin, currentSong, onSongClick, onReorder, onRemove }: QueueProps) {
  const [draggedIndex, setDraggedIndex] = React.useState<number | null>(null)

  const handleDragStart = (index: number) => {
    setDraggedIndex(index)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (index: number) => {
    if (draggedIndex === null || draggedIndex === index) {
      setDraggedIndex(null)
      return
    }
    
    const newQueue = [...songs]
    const draggedSong = newQueue[draggedIndex]
    newQueue.splice(draggedIndex, 1)
    newQueue.splice(index, 0, draggedSong)
    onReorder?.(newQueue)
    setDraggedIndex(null)
  }

  return (
    <div className="queue">
      <h2>Queue ({songs.length})</h2>
      {songs.length === 0 ? (
        <div className="empty-queue">Add songs to get started</div>
      ) : (
        <div className="queue-list">
          {songs.map((song, index) => (
            <div
              key={song.id}
              className={`queue-item ${currentSong?.id === song.id ? 'playing' : 'muted'} ${draggedIndex === index ? 'dragging' : ''}`}
              draggable={isAdmin}
              onDragStart={() => isAdmin && handleDragStart(index)}
              onDragOver={isAdmin ? handleDragOver : undefined}
              onDrop={() => isAdmin && handleDrop(index)}
              onClick={() => onSongClick?.(song)}
            >
              <div className="queue-item-info">
                <div className="queue-position">{index + 1}</div>
                <div className="queue-text">
                  <div className="queue-title">{song.title}</div>
                  <div className="queue-artist">{song.artist}</div>
                </div>
              </div>
              {isAdmin && (
                <div className="queue-actions">
                  <div className="drag-handle" title="Drag to reorder">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <circle cx="5" cy="4" r="1.5"/>
                      <circle cx="11" cy="4" r="1.5"/>
                      <circle cx="5" cy="8" r="1.5"/>
                      <circle cx="11" cy="8" r="1.5"/>
                      <circle cx="5" cy="12" r="1.5"/>
                      <circle cx="11" cy="12" r="1.5"/>
                    </svg>
                  </div>
                  <button
                    className="remove-btn"
                    onClick={(e) => { e.stopPropagation(); onRemove?.(song.id); }}
                    title="Remove"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                      <line x1="3" y1="3" x2="11" y2="11"/>
                      <line x1="11" y1="3" x2="3" y2="11"/>
                    </svg>
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
