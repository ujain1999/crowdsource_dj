const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function createRoom(roomName: string, userId?: string) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const response = await fetch(`${API_BASE}/api/rooms/create`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ name: roomName, user_id: userId }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to create room')
  }

  return await response.json()
}

export async function joinRoom(roomCode: string) {
  const response = await fetch(`${API_BASE}/api/rooms/${roomCode}/join`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to join room')
  }

  return await response.json()
}

export async function getRoomDetails(roomCode: string) {
  const response = await fetch(`${API_BASE}/api/rooms/${roomCode}`)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to get room details')
  }

  return await response.json()
}

export async function addSongToQueue(roomCode: string, url?: string, query?: string) {
  const response = await fetch(`${API_BASE}/api/songs/${roomCode}/add`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url, query }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to add song')
  }

  return await response.json()
}

export async function getMessages(roomCode: string) {
  const response = await fetch(`${API_BASE}/api/chat/${roomCode}/messages`)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to get messages')
  }

  return await response.json()
}

export async function sendMessage(roomCode: string, content: string, token: string) {
  const response = await fetch(`${API_BASE}/api/chat/${roomCode}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to send message')
  }

  return await response.json()
}
export async function removeSongFromQueue(roomCode: string, songId: string) {
  console.log(`Removing song ${songId} from queue in room ${roomCode}`)
  const response = await fetch(`${API_BASE}/api/songs/${roomCode}/songs/${songId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to remove song')
  }

  return await response.json()
}

export async function reorderQueue(roomCode: string, fromIndex: number, toIndex: number) {
  console.log(`Reordering queue in room ${roomCode}: ${fromIndex} -> ${toIndex}`)
  const response = await fetch(`${API_BASE}/api/songs/${roomCode}/queue/reorder`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ from_index: fromIndex, to_index: toIndex }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to reorder queue')
  }

  return await response.json()
}

export async function logout(token: string) {
  try {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
  } catch (e) {
    // Ignore network errors, continue with local logout
  }
}