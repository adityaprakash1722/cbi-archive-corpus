DATASET ?= aditya487/cbi-archive-corpus
SCRIPTS := outputs/cbi-research/scripts
ARCHIVE := outputs/cbi-archive/cbi-data
RESEARCH := outputs/cbi-research
INDEX := $(RESEARCH)/index/cbi-corpus-v5.2-5568docs.sqlite

.PHONY: help fetch index materialize reconcile recover scan-personal-data test test-invariants test-fresh-rebuild verify dataset release-artifacts clean-artifacts

help:
	@echo "fetch            pull the 48 MB Parquet corpus (set DATASET=user/name)"
	@echo "materialize      regenerate the Markdown corpus from the published Parquet"
	@echo "reconcile        make manifests/frontmatter match final page text"
	@echo "recover          re-extract page text the converter dropped (--ocr needs Tesseract)"
	@echo "scan-personal-data  screen the corpus for personal data before republishing"
	@echo "index            rebuild the v5.2 SQLite index from the Markdown corpus"
	@echo "test             classifier and synthetic Office regression suites"
	@echo "test-invariants  check tracked manifests agree with the docs, no network"
	@echo "test-fresh-rebuild  prove a clone can rebuild the index from published data"
	@echo "verify           re-hash every source and output, check page markers"
	@echo "dataset          regenerate publish/hf/data from the current index"
	@echo "release-artifacts regenerate Parquet plus every compressed audit manifest"
	@echo "clean-artifacts  list the 2.36 GB of superseded indices you can delete"

fetch:
	python3 $(SCRIPTS)/bootstrap.py --dataset $(DATASET)

index:
	python3 $(SCRIPTS)/build_search_index.py \
	  --corpus $(RESEARCH)/corpus --corpus $(RESEARCH)/corpus/office \
	  --audit-csv $(RESEARCH)/audit/pdf-audit.csv --output $(RESEARCH)/index \
	  --files-csv $(ARCHIVE)/manifests/files.csv --snapshot-date 2026-08-25 \
	  --page-authorship-csv $(RESEARCH)/qa/page-authorship-overrides.csv \
	  --authorship-overrides-csv $(RESEARCH)/qa/authorship-overrides.csv \
	  --extraction-preferences-csv $(RESEARCH)/qa/extraction-preferences.csv \
	  --database-name $(notdir $(INDEX))

materialize:
	python3 $(SCRIPTS)/materialize_markdown.py --user $(firstword $(subst /, ,$(DATASET))) \
	  --output $(RESEARCH)/corpus

reconcile:
	python3 $(SCRIPTS)/reconcile_final_text_metrics.py \
	  --corpus $(RESEARCH)/corpus --corpus $(RESEARCH)/corpus/office

test:
	cd $(SCRIPTS) && python3 test_classify_provenance.py
	cd $(SCRIPTS) && python3 test_convert_office.py

test-invariants:
	python3 $(SCRIPTS)/check_manifest_invariants.py

test-fresh-rebuild:
	python3 $(SCRIPTS)/test_fresh_rebuild.py --user $(firstword $(subst /, ,$(DATASET)))

verify:
	python3 $(SCRIPTS)/verify_raw_archive.py --archive $(ARCHIVE) --output $(RESEARCH)/qa
	python3 $(SCRIPTS)/reconcile_final_text_metrics.py \
	  --corpus $(RESEARCH)/corpus --corpus $(RESEARCH)/corpus/office --check
	python3 $(SCRIPTS)/validate_corpus.py --corpus $(RESEARCH)/corpus \
	  --corpus $(RESEARCH)/corpus/office \
	  --audit-csv $(RESEARCH)/audit/pdf-audit.csv --archive $(ARCHIVE) --output $(RESEARCH)/qa
	python3 $(SCRIPTS)/qa_extraction_quality.py \
	  --manifest $(RESEARCH)/corpus/conversion-manifest.csv \
	  --manifest $(RESEARCH)/corpus/office/conversion-manifest.csv \
	  --extraction-preferences-csv $(RESEARCH)/qa/extraction-preferences.csv \
	  --output $(RESEARCH)/qa

dataset:
	python3 $(SCRIPTS)/export_dataset.py --database $(INDEX) --output publish/hf/data

release-artifacts: dataset
	python3 publish/build_hf_release.py

recover:
	python3 $(SCRIPTS)/recover_lost_pages.py --database $(INDEX) \
	  --blobs publish/blobs --catalog publish/blob-catalog.csv \
	  --corpus $(RESEARCH)/corpus --output $(RESEARCH)/qa --ocr

scan-personal-data:
	python3 $(SCRIPTS)/scan_personal_data.py --database $(INDEX) --output $(RESEARCH)/qa

clean-artifacts:
	@echo "Superseded, safe to delete (2.36 GB):"
	@ls -la $(RESEARCH)/index/cbi-corpus-v3-5568docs.sqlite \
	        $(RESEARCH)/index/cbi-corpus-v2-5568docs.sqlite \
	        $(RESEARCH)/index/cbi-corpus.sqlite \
	        work/live-index/cbi-corpus.sqlite 2>/dev/null | awk '{printf "  %6.0f MB  %s\n",$$5/1e6,$$9}'
