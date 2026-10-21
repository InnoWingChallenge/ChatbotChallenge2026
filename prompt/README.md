# Location-based image knowledge records

All descriptions in this directory are written in English prose. Original image filenames and folder names are retained for traceability. Each `prompt.md` is a factual, image-grounded knowledge document intended for retrieval, rather than an instruction to generate another description. The records follow the supplied workflow: identify the location, describe visible text and spatial information separately, and retain both under the same location. They cover 119 photographs in 28 records: the original 33 JPEG photographs, 75 HEIC photographs from Pictures_Hzx, and 11 JPEG photographs from submission_repo/image_hzq. Existing locations incorporate the additional evidence in their original records; nine newly documented locations or circulation/display areas have their own records. The four original standalone-image folders and the nested Wet Lab - Culture Room record are retained.

Each subject is described in connected paragraphs. Short headings separate related topics, and source-image links preserve attribution. Visible wording, colors, counts and spatial relationships are included where supported. Counts refer to the visible image rather than an assumed complete inventory. Unreadable text, unknown locations and conflicting notices remain explicit. Document dates do not establish the image capture date, and photographed rules or telephone numbers have not been verified as current.

For Chroma ingestion, split these documents at paragraph or topic boundaries and retain the location name with every resulting chunk. If a paragraph is too long for the configured embedding model, split it at sentence boundaries. Carry the source links, record path, section title and chunk position as metadata; also retain `kind=image_description`, the actual image content type (`image/jpeg` or `image/heic`), the review date `2026-10-13`, and an unknown capture date. The original image path is the stable local source identifier. Preserve multiple source links when a section combines images. Unknown-location records must remain unknown rather than acquiring a room name from a nearby record. Avoid indexing this README as factual evidence about the building.

Embedding these records and adding them to Chroma makes them retrievable knowledge; it does not train or fine-tune the chatbot model. These files have not yet been embedded or imported into Chroma. Keep the raw images separate so descriptions and the database can be rebuilt. Future additions to this directory should continue using English paragraphs with the same source attribution and evidence boundaries.

## Records

[Brainstorm Space / Brainstorming Area](Brainstorm_Space/prompt.md)

[Digital Learning Studio](Digital_Learning_Studio/prompt.md)

[Dream Chamber](Dream_Chamber/prompt.md)

[Multi-Purpose Room](Multi-Purpose_Room/prompt.md)

[Podcast Studio](Podcast_Studio/prompt.md)

[Project Studio A](Project_Studio_A/prompt.md)

[Project Studio B](Project_Studio_B/prompt.md)

[Thematic Workshop D](Thematic_Workshop_D/prompt.md)

[Thematic Workshop E](Thematic_Workshop_E/prompt.md)

[Wet Lab - Culture Room](Thematic_Workshop_G/Wet_Lab_Culture_Room/prompt.md)

[Machine Workshop](Machine_Workshop/prompt.md)

[Open Event Area](Open_Event_Area/prompt.md)

[Thematic Workshop F](Thematic_Workshop_F/prompt.md)

[Thematic Workshop G](Thematic_Workshop_G/prompt.md)

[Thematic Workshop H](Thematic_Workshop_H/prompt.md)

[Innovation Wing student research assistant entry notice](微信图片_20261013104634_77_35/prompt.md)

[Tam Wing Fan Innovation Fund funding poster](微信图片_20261013104642_85_35/prompt.md)

[LG directional sign](微信图片_20261013104643_86_35/prompt.md)

[Electronics workbench at an unidentified location](微信图片_20261013104644_87_35/prompt.md)


## Additional location records from Pictures_Hzx

[Conference Room (IW-G02)](Conference_Room/prompt.md)

[Thematic Workshop A](Thematic_Workshop_A/prompt.md)

[Thematic Workshop B](Thematic_Workshop_B/prompt.md)

[Thematic Workshop C](Thematic_Workshop_C/prompt.md)

[Makerspace A](Makerspace_A/prompt.md)

[Ground-floor entrance and reception surroundings](Ground_Floor_Entrance/prompt.md)

[Entrance history display](Entrance_History_Display/prompt.md)

[Restroom approach](Restrooms/prompt.md)

[Photographed fire-exit and glazed-door surroundings](Fire_Exits/prompt.md)

The [Pictures_Hzx source manifest](pictures_hzx_manifest.json) records all 75 original HEIC paths, SHA-256 hashes, destination documents and section titles. Source folder labels were treated as hints: visible plaques take precedence. Photos of Thematic Workshop H and Dream Chamber filed under Brainstorming Area were reassigned to their named rooms. A separate same-name DreamChamber glazing view remains explicitly unresolved rather than supplying an assumed LG14 interior.


## Additional evidence from image_hzq

All seven introduction-board photographs are merged into [Entrance history display](Entrance_History_Display/prompt.md). The three maker-space views and one rules sign are merged into [Makerspace A](Makerspace_A/prompt.md), with their visual location match explicitly qualified because these JPEGs do not display an A designation. No duplicate location folders were created. The [image_hzq source manifest](image_hzq_manifest.json) records the 11 image paths, hashes, document sections and location-attribution basis.
