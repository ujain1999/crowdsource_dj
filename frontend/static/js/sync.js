socket.on('connect', function () {
    console.log('Connected to server!');
});

// Handle welcome message
socket.on('message', function (data) {
    console.log('Server: ' + data.data);
});

// Handle server responses
socket.on('response', function (data) {
    console.log('Response: ' + data.data);
});

socket.on('sync', function(data) {
    console.log('Sync event received:', data);

    // Avoid syncing if this client initiated the change
    if (data.sid === socket.id) {
        console.log('Sync event from self, ignoring.');
        return;
    }

    if (data.action === 'play') {
        console.log('Syncing play action');
        player.play(sync=true);
    } 
    else if (data.action === 'pause') {
        console.log('Syncing pause action');
        player.pause(sync=true);
    }

});