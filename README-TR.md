# WearForce-Clean - Yerel Kurulum Rehberi 🚀

Kanka! Bu proje WearForce-Clean isimli React + TypeScript tabanlı web uygulaması. Aşağıdaki adımları takip ederek kolayca kendi bilgisayarında çalıştırabilirsin.

## 📋 Gereksinimler

Başlamadan önce bilgisayarında bunların kurulu olması lazım:

- **Node.js 18+** - [nodejs.org](https://nodejs.org) adresinden indir
- **Git** - [git-scm.com](https://git-scm.com) adresinden indir
- **Docker Desktop** (isteğe bağlı) - Backend servisleri için

## 🛠️ Kurulum Adımları

### 1. Projeyi İndir
```bash
git clone https://github.com/CankatSarac/wearforce-clean.git
cd wearforce-clean
```

### 2. Web Uygulamasını Çalıştır

Kanka, en kolay yol bu - sadece web uygulamasını çalıştıralım:

```bash
# Web klasörüne git
cd clients/web

# Bağımlılıkları yükle
npm install

# Uygulamayı başlat
npm run dev
```

Bu kadar! Artık tarayıcından `http://localhost:3001` adresine gidebilirsin.

### 3. Backend Servisleri (İsteğe Bağlı)

Eğer tam işlevli uygulama istiyorsan, Docker ile backend servislerini de çalıştırabilirsin:

```bash
# Ana dizine dön
cd ../..

# Backend servislerini başlat
cd services
docker compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d

# Gateway servislerini başlat
cd ../gateway
docker compose -f docker-compose.yml -f docker-compose.clean.override.yml up -d
```

## 🔧 Port Konfigürasyonu

Bu proje orijinal WearForce projesi ile çakışmayacak şekilde ayarlanmış:

| Servis | Orijinal Port | Clean Port |
|--------|---------------|------------|
| Web App | 3000 | **3001** |
| Gateway | 8080 | 8180 |
| GraphQL | 8000 | 9000 |
| Database | 5432 | 5532 |
| Redis | 6379 | 6479 |

## 🚨 Sorun Giderme

### Node.js Kurulu Değilse
```bash
# Windows için Chocolatey kullan
choco install nodejs

# Veya nodejs.org adresinden indir
```

### Port Zaten Kullanılıyorsa
Eğer 3001 portu meşgulse, şu komutu kullan:
```bash
npm run dev -- --port 3002
```

### Docker Çalışmıyorsa
Docker Desktop'ı açmayı unutma! Başlatmak için:
- Windows: Docker Desktop uygulamasını aç
- Mac: Docker Desktop uygulamasını aç

## 🎯 Ne Yapabilirim?

Artık şunları yapabilirsin:
- ✅ Web uygulamasını geliştir
- ✅ Kod değişikliklerini canlı olarak gör (hot reload)
- ✅ Yeni özellikler ekle
- ✅ UI/UX iyileştirmeleri yap

## 📱 Mobil Uygulama (İsteğe Bağlı)

Mobil uygulamayı da çalıştırmak istersen:

```bash
cd clients/mobile
npm install
npm start

# iOS için (Mac gerekli)
npm run ios

# Android için
npm run android
```

## 🆘 Yardım Lazım?

Kanka bir sorun yaşarsan:
1. Terminal'de hata mesajını kontrol et
2. Port'ların boş olduğundan emin ol
3. Node.js ve npm'in son sürümde olduğunu kontrol et
4. GitHub Issues'a yaz: [github.com/CankatSarac/wearforce-clean/issues](https://github.com/CankatSarac/wearforce-clean/issues)

## 🚀 Hızlı Başlangıç (TL;DR)

Acelen varsa sadece şunları yap:
```bash
git clone https://github.com/CankatSarac/wearforce-clean.git
cd wearforce-clean/clients/web
npm install
npm run dev
```

Tarayıcıda `http://localhost:3001` aç ve keyif çıkar! 🎉

---

**Not**: Bu proje React + TypeScript + Vite kullanıyor. Modern ve hızlı bir geliştirme deneyimi sunuyor!

**Kolay gelsin kanka! 🤝**
