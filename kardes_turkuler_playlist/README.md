# Kardeş Türküler - Kürtçe & Zazaca Playlist

`songs.json` içinde Kardeş Türküler'in Kürtçe (Kurmancî) ve Zazaca
söylenen, doğrulanmış parçalarının listesi bulunuyor. `create_playlist.py`
bu listeyi kullanarak Spotify hesabınızda otomatik bir playlist oluşturur.

## Kurulum

1. https://developer.spotify.com/dashboard adresine kendi Spotify
   hesabınızla giriş yapın.
2. "Create app" ile yeni bir uygulama oluşturun. Redirect URI olarak
   `http://127.0.0.1:8888/callback` girin ve "Web API" iznini seçin.
3. Uygulamanın Client ID ve Client Secret değerlerini kopyalayın.
4. Ortam değişkenlerini ayarlayın:

   ```bash
   export SPOTIPY_CLIENT_ID="client_id_buraya"
   export SPOTIPY_CLIENT_SECRET="client_secret_buraya"
   export SPOTIPY_REDIRECT_URI="http://127.0.0.1:8888/callback"
   ```

5. Bağımlılığı kurun:

   ```bash
   pip install -r requirements.txt
   ```

6. Script'i kendi bilgisayarınızda çalıştırın:

   ```bash
   python create_playlist.py
   ```

   Bu adımda tarayıcınız açılacak, Spotify hesabınızla giriş yapıp izin
   vermeniz istenecek. İzin verdikten sonra script playlist'i hesabınızda
   otomatik oluşturup parçaları ekleyecek.

Script'i bu repodan, kendi bilgisayarınızdan veya kendi Spotify
hesabınıza tarayıcı erişimi olan bir ortamdan çalıştırmanız gerekir;
yetkilendirme adımı sizin Spotify girişinizi gerektirdiği için
otomatik/sunucu taraflı ortamlarda çalışmaz.
