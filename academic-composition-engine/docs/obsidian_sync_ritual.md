# Obsidian Sync Ritual (operational)

Scop: păstrăm separarea clară authoring vs execution și facem sync-ul rutină, nu excepție.

## Când rulezi sync

Rulează obligatoriu:
1. după orice sesiune importantă de lucru în Obsidian;
2. înainte de testarea `devil's advocate`;
3. înainte de release.

## Comandă standard

```bash
ace sync-obsidian-knowledge --vault-dir ./obsidian/vault_minimal
```

Pentru rulare strictă (fail la notă invalidă):

```bash
ace sync-obsidian-knowledge --vault-dir ./obsidian/vault_minimal --strict
```

## Verificare rapidă

```bash
ace inspect-anti-prompts --stage drafting
```

Confirmă că există entries active în snapshot-ul compilat.

## KPI pentru devil's advocate (valoare reală)

La fiecare 5-10 secțiuni evaluate, urmărește:
- `useful_red_flags`: câte semnale chiar au dus la corecții utile;
- `false_positives`: câte semnale au fost zgomot;
- `review_time_per_section_min`: timpul mediu de review uman pe secțiune.

Țintă operațională:
- trend descendent pentru `false_positives`;
- trend descendent pentru `review_time_per_section_min`;
- menținere/creștere pentru `useful_red_flags`.

## Research-MCP boundary

`research-mcp` este strict discovery layer:
- Google: leads;
- YouTube: context și explicații;
- Reddit: contraargumente și obiecții reale.

Aceste rezultate NU intră direct în bibliografie academică fără filtrare și validare în pipeline-ul intern.
