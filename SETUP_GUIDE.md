# Backend Setup Guide - Authentication + MongoDB

## Prerequisites

1. **Python 3.8+**
2. **MongoDB** (Local or Cloud)
   - Local: Download from https://www.mongodb.com/try/download/community
   - Cloud: Use MongoDB Atlas (free tier available)

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements_v2.txt
```

### 2. Configure Environment

Edit `.env` file:

```env
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=vehicle_diagnostic_db
JWT_SECRET=your-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

For MongoDB Atlas:
```env
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
```

### 3. Start MongoDB (if local)

```bash
# Windows
mongod

# Linux/Mac
sudo systemctl start mongod
```

### 4. Run the Server

```bash
python main_v2.py
```

Server runs at: `http://127.0.0.1:8001`

## API Documentation

### Authentication Endpoints

#### Register User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe"
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {...}
}
```

### Vehicle Endpoints (Protected)

All vehicle endpoints require `Authorization: Bearer <token>` header.

#### Create Vehicle
```http
POST /vehicles
Authorization: Bearer <token>
Content-Type: application/json

{
  "vin": "1HGBH41JXMN109186",
  "make": "Toyota",
  "model": "Corolla",
  "year": 2020,
  "fuel_type": "Gasoline"
}
```

#### Get All Vehicles
```http
GET /vehicles
Authorization: Bearer <token>
```

#### Get Single Vehicle
```http
GET /vehicles/{vehicle_id}
Authorization: Bearer <token>
```

#### Delete Vehicle
```http
DELETE /vehicles/{vehicle_id}
Authorization: Bearer <token>
```

### Diagnostic Endpoints (Protected)

#### Run Diagnostic
```http
POST /diagnostics
Authorization: Bearer <token>
Content-Type: application/json

{
  "vehicle_id": "507f1f77bcf86cd799439011",
  "sensor_data": {
    "ENGINE_COOLANT_TEMP": 88,
    "ENGINE_LOAD": 45,
    "ENGINE_RPM": 1800,
    "FUEL_PRESSURE": 50,
    "MAF": 8
  },
  "mark": "toyota",
  "model_name": "corolla"
}

Response:
{
  "id": "...",
  "has_fault": false,
  "confidence": 0.92,
  "status": "Healthy",
  "severity": "HEALTHY",
  "analysis": {
    "abnormal_sensors": [],
    "recommendations": [],
    "warnings": []
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

#### Get Diagnostic History
```http
GET /diagnostics?vehicle_id={vehicle_id}
Authorization: Bearer <token>
```

#### Get Single Diagnostic
```http
GET /diagnostics/{diagnostic_id}
Authorization: Bearer <token>
```

## Testing

Run the comprehensive test script:

```bash
python test_full_api.py
```

This will test:
1. User registration
2. User login
3. Vehicle creation
4. Vehicle retrieval
5. Normal diagnostic
6. Critical diagnostic
7. Diagnostic history
8. Unauthorized access

## MongoDB Collections

### users
```json
{
  "_id": ObjectId,
  "email": "user@example.com",
  "password_hash": "hashed_password",
  "full_name": "John Doe",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### vehicles
```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "vin": "1HGBH41JXMN109186",
  "make": "Toyota",
  "model": "Corolla",
  "year": 2020,
  "fuel_type": "Gasoline",
  "created_at": ISODate
}
```

### diagnostics
```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "vehicle_id": ObjectId,
  "has_fault": false,
  "confidence": 0.92,
  "status": "Healthy",
  "severity": "HEALTHY",
  "sensor_data": {...},
  "analysis": {...},
  "timestamp": ISODate
}
```

## Security Features

✅ Password hashing with bcrypt  
✅ JWT token authentication  
✅ Protected endpoints  
✅ User-specific data isolation  
✅ Token expiration (30 minutes default)

## Interactive API Docs

Visit: `http://127.0.0.1:8001/docs`

FastAPI provides automatic interactive documentation where you can:
- Test all endpoints
- See request/response schemas
- Authenticate with JWT tokens

## Troubleshooting

### MongoDB Connection Error
- Ensure MongoDB is running
- Check MONGODB_URL in .env
- Verify network connectivity (for Atlas)

### Import Errors
- Install all dependencies: `pip install -r requirements_v2.txt`
- Check Python version (3.8+)

### Token Errors
- Ensure JWT_SECRET is set in .env
- Check token expiration time
- Verify Authorization header format: `Bearer <token>`

## Next Steps

1. ✅ Authentication implemented
2. ✅ MongoDB integration complete
3. ✅ Vehicle management ready
4. ✅ Diagnostic history tracking
5. 🔄 Mobile app integration (next)
6. 🔄 Trend analysis
7. 🔄 Push notifications
