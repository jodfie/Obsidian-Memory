# Whiskey & Cigar Inventory System - Project Plan
*Project for Matt's collection - 130-140 bottles, 2 locations*
*Date: 2026-01-28*

## Project Overview
**Goal**: Self-hosted web app for managing whiskey + cigar inventory with AI-powered pairing suggestions
**Primary User**: Matt (extensive whiskey collection, expanding to cigars)
**Platform**: Mobile-first web app, self-hosted on redleif.dev
**Key Differentiator**: AI suggestions based on mood, weather, conversation

## Requirements Analysis

### Collection Details
- **Whiskey**: ~130-140 bottles
- **Locations**: Office shelf, Garage
- **Current System**: None (starting from scratch)
- **Priority**: Tasting notes functionality
- **Access Pattern**: Mobile-first usage

### Core Features Needed

#### **Inventory Management**
**Whiskey Fields:**
- Basic: Distillery, Name, Age, Country, Region, Category
- Technical: ABV, Volume, Cask Type, Bottling Date
- Personal: Purchase Price, Date, Vendor, Location (Office/Garage)
- Status: Open/Sealed, Amount Remaining
- **Priority**: Tasting Notes, Personal Rating, Date Tasted

**Cigar Fields:**
- Basic: Brand, Name, Size (Ring/Length), Country, Region
- Technical: Wrapper, Binder, Filler, Strength
- Personal: Purchase Price, Date, Vendor, Storage Location
- Status: Individual vs Box, Quantity, Humidity Notes
- **Priority**: Tasting Notes, Personal Rating, Date Smoked

#### **AI Pairing Engine**
**Input Factors:**
- Current weather/temperature
- Time of day/season  
- Mood indicators (celebratory, relaxed, contemplative)
- Conversation context
- Previous ratings/preferences
- Available inventory

**Suggestion Types:**
- Whiskey recommendations based on mood/weather
- Cigar recommendations based on mood/weather
- Whiskey + Cigar pairings
- Special occasion recommendations
- "What should I try next?" suggestions

## Technical Architecture

### **Stack Selection** (redleif.dev hosted)
- **Frontend**: Next.js 14 (React, TypeScript)
- **Backend**: Node.js/Express API
- **Database**: PostgreSQL (complex queries, JSON support)
- **AI**: Integration with Claude API for pairing logic
- **Storage**: Local file storage for photos
- **Auth**: JWT or session-based (simple, self-hosted)

### **Database Schema Design**

**Whiskey Table:**
```sql
whiskey_inventory (
  id, distillery, name, age, country, region, category,
  abv, volume_ml, cask_type, bottling_date,
  purchase_price, purchase_date, vendor, location,
  status, amount_remaining, 
  tasting_notes, personal_rating, date_tasted,
  photo_url, created_at, updated_at
)
```

**Cigar Table:**
```sql
cigar_inventory (
  id, brand, name, size_ring, size_length, country, region,
  wrapper, binder, filler, strength,
  purchase_price, purchase_date, vendor, storage_location,
  quantity, humidity_notes,
  tasting_notes, personal_rating, date_smoked,
  photo_url, created_at, updated_at
)
```

**Tasting Sessions:**
```sql
tasting_sessions (
  id, type (whiskey/cigar/pairing), whiskey_id, cigar_id,
  date, weather, mood, occasion, notes, rating,
  pairing_success (if both), created_at
)
```

### **AI Pairing Logic**

**Weather-Based Suggestions:**
- **Hot/Humid**: Light whiskies (Highland, Lowland), milder cigars
- **Cold/Dry**: Peated Scotch, full-bodied cigars
- **Rainy**: Comfort drams (sherry casks, medium cigars)

**Mood-Based Suggestions:**
- **Celebratory**: Premium bottles, special cigars
- **Relaxed**: Easy-drinking, familiar profiles
- **Contemplative**: Complex, nuanced selections
- **Social**: Crowd-pleasers, conversation starters

**Time-Based Logic:**
- **Morning/Afternoon**: Lighter profiles
- **Evening**: Fuller bodies welcome
- **Late Night**: Digestif-style, contemplative choices

## Development Phases

### **Phase 1: Core Inventory (4-6 weeks)**
- [ ] Database setup and schema
- [ ] Basic CRUD for whiskey inventory
- [ ] Mobile-responsive UI (inventory list, detail views)
- [ ] Location management (Office/Garage)
- [ ] Photo upload functionality
- [ ] Basic search and filtering

### **Phase 2: Cigar Integration (2-3 weeks)**
- [ ] Cigar inventory CRUD
- [ ] Unified search across both inventories
- [ ] Enhanced filtering (by type, location, rating)
- [ ] Inventory analytics dashboard

### **Phase 3: Tasting Notes System (2-3 weeks)**
- [ ] Detailed tasting note forms
- [ ] Rating system with personal scales
- [ ] Tasting history and progression tracking
- [ ] Quick "tried this" mobile workflow

### **Phase 4: AI Pairing Engine (3-4 weeks)**
- [ ] Weather API integration
- [ ] Mood/occasion input interface
- [ ] Claude API integration for pairing logic
- [ ] Suggestion algorithm development
- [ ] Conversation-based recommendations

### **Phase 5: Advanced Features (2-3 weeks)**
- [ ] Market value tracking
- [ ] Backup/export functionality
- [ ] Advanced analytics
- [ ] Notification system (low stock, aging reminders)

## Deployment Architecture

### **redleif.dev Integration**
- **Domain**: whiskey.redleif.dev or similar
- **SSL**: Let's Encrypt via Authelia/Traefik
- **Database**: PostgreSQL container
- **App**: Docker containerized Next.js app
- **Backup**: Automated daily backups to storage
- **Monitoring**: Integration with existing Uptime Kuma

### **Security Considerations**
- Private access only (no public registration)
- Secure photo storage
- Regular database backups
- API rate limiting for AI calls

## AI Suggestion Engine Details

### **Pairing Logic Framework**
**Profile Matching:**
- Whiskey flavor profiles (sweet, spicy, smoky, fruity)
- Cigar strength/flavor profiles
- Complementary vs contrasting pairing approaches

**Context-Aware Suggestions:**
```javascript
// Example logic
if (weather.temp > 80 && mood === 'relaxed') {
  suggest: {
    whiskey: Highland/Lowland, light body,
    cigar: Connecticut wrapper, mild strength,
    pairing: "Light and refreshing combination for hot weather relaxation"
  }
}
```

### **Learning & Adaptation**
- Track user ratings of suggestions
- Learn personal preferences over time
- Adjust algorithms based on successful pairings
- Build personal preference profiles

## Next Steps

1. **Technical Setup**: Set up development environment on redleif.dev
2. **Database Design**: Finalize schema and create migrations
3. **UI/UX Planning**: Create wireframes for mobile-first design
4. **AI Integration Planning**: Design Claude API integration approach
5. **Begin Phase 1 Development**

## Notes
- Focus on mobile-first experience (Matt's primary usage)
- Emphasize tasting notes as the priority feature
- Build AI pairing as the standout differentiator
- Keep self-hosted, private, and secure
- Plan for easy data export/backup