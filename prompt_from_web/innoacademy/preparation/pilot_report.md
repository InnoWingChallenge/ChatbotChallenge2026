# Image description pilot: 2026-10-17

Status: steps 1-5 pilot complete; no production index changes.

```json
{
  "inventory": {
    "physical_photos": 119,
    "website_urls": 6584,
    "file_states": {
      "verified": 177,
      "missing": 6500,
      "hash_changed": 24,
      "captured_without_prior_hash": 2
    }
  },
  "recovered_urls": 84,
  "recovered_bytes": 144209195,
  "matching_historical_hash": 58,
  "changed_bytes_held_back": 24,
  "fingerprinted_images": 203,
  "decode_failures": 0,
  "near_duplicate_pairs": 5,
  "cross_source_near_pairs": 0,
  "verified_exact_duplicate_groups": 0,
  "pilot_descriptions": 20,
  "model_counts": {
    "gpt-6-sol": 10,
    "gpt-6-luna": 10
  },
  "independent_visual_spot_checks": 4,
  "ingested": false,
  "new_downloads_without_prior_hash": 2
}
```

## Description index

The raw and preview links require this worktree cache; raw bytes are intentionally not committed.

| # | Model (low) | Title | Description | Preview |
|---|---|---|---|---|
| 1 | gpt-6-sol | HKU DBF Team poster | [draft](../pilot_descriptions/3024e716705c54d7605f5e98/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/3024e716705c54d7605f5e98.jpg) |
| 2 | gpt-6-luna | SMART PRODUCT DEVELOPMENT — Automated Guided Vehicle | [draft](../pilot_descriptions/92d23cb2026e981d614bec9b/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/92d23cb2026e981d614bec9b.jpg) |
| 3 | gpt-6-sol | IOP CONTROLLABLE GOGGLES poster | [draft](../pilot_descriptions/f73173354e5f6a8b418c9a70/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/f73173354e5f6a8b418c9a70.jpg) |
| 4 | gpt-6-luna | Playing Chess With A Robotic Arm | [draft](../pilot_descriptions/13f90d178de56d8fd69def8b/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/13f90d178de56d8fd69def8b.jpg) |
| 5 | gpt-6-sol | ROBOTA GO-FIGHTING SPEED poster | [draft](../pilot_descriptions/3197741a8a0745ab07406f6b/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/3197741a8a0745ab07406f6b.jpg) |
| 6 | gpt-6-luna | Smart Soccer Robot | [draft](../pilot_descriptions/64168bb7caa4aa8f41bfe6a0/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/64168bb7caa4aa8f41bfe6a0.jpg) |
| 7 | gpt-6-sol | ROBOT ARM CHALLENGE SPRING 2026 Season poster | [draft](../pilot_descriptions/75a2bf1d64da73c23786b0f2/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/75a2bf1d64da73c23786b0f2.jpg) |
| 8 | gpt-6-luna | Advanced Level Firmware Programming for Legged Robot | [draft](../pilot_descriptions/77cc3e542e8f7f62850a5fa0/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/77cc3e542e8f7f62850a5fa0.jpg) |
| 9 | gpt-6-sol | ROBOT ARM CHALLENGE Workshop 2 of 3 poster | [draft](../pilot_descriptions/83865e84cfae48a6dd2c2cd9/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/83865e84cfae48a6dd2c2cd9.jpg) |
| 10 | gpt-6-luna | 3D Printed Robot Dog Walking on Terrain for STEM Education | [draft](../pilot_descriptions/8e29f45a80d619fda4378a73/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/8e29f45a80d619fda4378a73.jpg) |
| 11 | gpt-6-sol | RAI: DOGGI-E poster | [draft](../pilot_descriptions/8f4f08ec97bb128ebb2c9448/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/8f4f08ec97bb128ebb2c9448.jpg) |
| 12 | gpt-6-luna | Smart Soccer Robot | [draft](../pilot_descriptions/dbb08a382bd737cc5a130303/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/dbb08a382bd737cc5a130303.jpg) |
| 13 | gpt-6-sol | Unleashing the Power of AI and Robots recruitment workshop | [draft](../pilot_descriptions/dce95cf4211dc0ebcb0bdd96/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/dce95cf4211dc0ebcb0bdd96.jpg) |
| 14 | gpt-6-luna | LEAPS “LOCAL ENVIRONMENT ALLIANCE” PROJECT SERIES | [draft](../pilot_descriptions/0d0d0515f867eafb1711116c/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/0d0d0515f867eafb1711116c.jpg) |
| 15 | gpt-6-sol | The 9th Engineering Inno Show call for student projects | [draft](../pilot_descriptions/1caf4c932d22c001584dcee3/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/1caf4c932d22c001584dcee3.jpg) |
| 16 | gpt-6-luna | The 8th Engineering Inno Show — Call for Student Projects | [draft](../pilot_descriptions/f864753c0f081ab663d281ad/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/f864753c0f081ab663d281ad.jpg) |
| 17 | gpt-6-sol | The Library game project poster | [draft](../pilot_descriptions/0450fb0141500e55757e98e7/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/0450fb0141500e55757e98e7.jpg) |
| 18 | gpt-6-luna | Datax | [draft](../pilot_descriptions/1df53e334bc583f4f50c2f99/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/1df53e334bc583f4f50c2f99.jpg) |
| 19 | gpt-6-sol | TOGGLE adhesive Wi-Fi smart wall switch robot poster | [draft](../pilot_descriptions/204f6b406f14c74f78571aac/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/204f6b406f14c74f78571aac.jpg) |
| 20 | gpt-6-luna | SNAKE 4D | [draft](../pilot_descriptions/25ba36d8165967cdd7141ca9/prompt.md) | [image](../../../submission_repo/data/web_academy/previews/25ba36d8165967cdd7141ca9.jpg) |

## Scope and next actions

- 6,584 website URL records and 119 local originals inventoried. Historical status is preserved.
- Recovered 24 previously reviewed-image URLs plus 60 pilot candidate URLs; this is not recovery of the full 3.9 GB archive.
- 24 recovered byte streams differ from historical SHA-256. Their old descriptions were not reused or overwritten; they are excluded from this new description batch pending version review.
- Cross-source similarity covered the 84 recovered website images and all 119 local originals, including HEIC. It does not establish absence of duplicates across the whole undownloaded collection.
- Two URLs had no historical hash and are recorded as new captures, not changed content.
- 5 near-duplicate pairs retained as candidates; no raw image deleted. Different viewpoints may be complementary.
- 20 pilot drafts are outside the production descriptions registry, so normal image ingestion does not pick them up accidentally.
- Four images were visually spot-checked; see [quality_review.json](quality_review.json). Small-print omissions remain on some posters.
- No online embedding or Chroma writes were performed. Current database and previous evaluation reports were preserved.
