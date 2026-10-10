# FastAPI Richtlinien & Best Practices

1. **Routen & Endpunkte**:
   - Deklariere I/O-intensive Endpunkte asynchron mit `async def`.
   - Verwende sprechende HTTP-Statuscodes und strukturierte `APIRouter`-Module.

2. **Datenvalidierung & Schemas**:
   - Verwende Pydantic v2 `BaseModel` für alle Request-Bodys und Response-Modelle.
   - Validiere Eingaben strikt und fange Fehler mit geeigneten HTTPExceptions ab.

3. **Dependency Injection**:
   - Nutze `Depends()` für Datenbank-Sessions, Authentifizierung und Service-Klassen.
