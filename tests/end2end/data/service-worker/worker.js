self.addEventListener('install', event => {
    console.log("Installing service worker");
    event.waitUntil(
      caches.open('example-cache')
        .then(cache => cache.add('data.json'))
        .then(self.skipWaiting())
    );
});
