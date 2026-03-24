import React, { createContext, useContext, useState, useCallback } from 'react'

export interface Song {
  id: string
  song_id: string
  title: string
  artist: string
  duration: number
  thumbnail?: string
  url: string
  added_by: string
  position: number
}

export interface ChatMessage {
  id: string
  content: string
  user: {
    id: string
    username: string
    is_guest: boolean
    created_at: string
  }
  created_at: string
}

export interface RoomUser {
  id: string
  username: string
}

interface PlaybackState {
  isPlaying: boolean
  currentTime: number
  duration: number
}

interface RoomContextType {
  currentSong: Song | null
  queue: Song[]
  messages: ChatMessage[]
  roomUsers: RoomUser[]
  playbackState: PlaybackState
  isAdmin: boolean
  roomName: string

  setCurrentSong: (song: Song | null) => void
  addToQueue: (song: Song) => void
  removeFromQueue: (songId: string) => void
  reorderQueue: (songs: Song[]) => void
  addMessage: (message: ChatMessage) => void
  setRoomUsers: (users: RoomUser[]) => void
  setPlaybackState: (state: PlaybackState) => void
  setIsAdmin: (isAdmin: boolean) => void
  setRoomName: (name: string) => void
  addRoomUser: (user: RoomUser) => void
}

const RoomContext = createContext<RoomContextType | undefined>(undefined)

export function RoomProvider({ children }: { children: React.ReactNode }) {
  const [currentSong, setCurrentSong] = useState<Song | null>(null)
  const [queue, setQueue] = useState<Song[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [roomUsers, setRoomUsers] = useState<RoomUser[]>([])
  const [playbackState, setPlaybackState] = useState<PlaybackState>({
    isPlaying: false,
    currentTime: 0,
    duration: 0,
  })
  const [isAdmin, setIsAdmin] = useState(false)
  const [roomName, setRoomName] = useState('')

  const addToQueue = useCallback((song: Song) => {
    setQueue(prev => {
      // Prevent duplicates by checking if song already exists
      if (prev.some(s => s.id === song.id)) {
        return prev
      }
      return [...prev, song]
    })
  }, [])

  const removeFromQueue = useCallback((songId: string) => {
    setQueue(prev => prev.filter(s => s.id !== songId))
  }, [])

  const reorderQueue = useCallback((songs: Song[]) => {
    setQueue(songs)
  }, [])

  const addMessage = useCallback((message: ChatMessage) => {
    setMessages(prev => [...prev, message])
  }, [])

  const addRoomUser = useCallback((user: RoomUser) => {
    setRoomUsers(prev => [...prev, user])
  }, [])

  return (
    <RoomContext.Provider
      value={{
        currentSong,
        queue,
        messages,
        roomUsers,
        playbackState,
        isAdmin,
        roomName,
        setCurrentSong,
        addToQueue,
        removeFromQueue,
        reorderQueue,
        addMessage,
        setRoomUsers,
        setPlaybackState,
        setIsAdmin,
        setRoomName,
        addRoomUser,
      }}
    >
      {children}
    </RoomContext.Provider>
  )
}

export function useRoom() {
  const context = useContext(RoomContext)
  if (!context) {
    throw new Error('useRoom must be used within RoomProvider')
  }
  return context
}
