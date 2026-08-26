DATASET ?= aditya487/cbi-archive-corpus
SCRIPTS := outputs/cbi-research/scripts
ARCHIVE := outputs/cbi-archive/cbi-data
RESEARCH := outputs/cbi-research
INDEX := $(RESEARCH)/index/cbi-corpus-v3-5568docs.sqlite

.PHONY: help fetch index materialize test verify dataset clean-artifacts

help:
	@echo "fetch            pull the 47 MB Parquet corpus (set DATASET=user/name)"
	@echo "materialize      regenerate the Markdown corpus from the published Parquet"
	@echo "index            rebuild the v3 SQLite index from the Markdown corpus"
	@echo "test             classifier regression suite, 94 assertions"
	@echo "verify           re-hash every source and output, check page markers"
	@echo "dataset          regenerate publish/hf/data from the current index"
	@echo "clean-artifacts  list the 1.7 GB of superseded indices you can delete"

fetch:
	python3 $(SCRIPTS)/bootstrap.py --dataset $(DATASET)

index:
	python3 $(SCRIPTS)/build_search_index.py \
	  --corpus $(RESEARCH)/corpus --corpus $(RESEARCH)/corpus/office \
	  --audit-csv $(RESEARCH)/audit/pdf-audit.csv --output $(RESEARCH)/index \
	  --database-name $(notdir $(INDEX))

materialize:
	python3 $(SCRIPTS)/materialize_markdown.py --user $(firstword $(subst /, ,$(DATASET))) \
	  --output $(RESEARCH)/corpus/markdown

test:
	cd $(SCRIPTS) && python3 test_classify_provenance.py

verify:
	python3 $(SCRIPTS)/validate_corpus.py --corpus $(RESEARCH)/corpus \
	  --audit-csv $(RESEARCH)/audit/pdf-audit.csv --archive $(ARCHIVE) --output $(RESEARCH)/qa
	python3 $(SCRIPTS)/qa_extraction_quality.py \
	  --manifest $(RESEARCH)/corpus/conversion-manifest.csv \
	  --manifest $(RESEARCH)/corpus/office/conversion-manifest.csv --output $(RESEARCH)/qa

dataset:
	python3 $(SCRIPTS)/export_dataset.py --database $(INDEX) --output publish/hf/data

clean-artifacts:
	@echo "Superseded, safe to delete (1.70 GB):"
	@ls -la $(RESEARCH)/index/cbi-corpus-v2-5568docs.sqlite \
	        $(RESEARCH)/index/cbi-corpus.sqlite \
	        work/live-index/cbi-corpus.sqlite 2>/dev/null | awk '{printf "  %6.0f MB  %s\n",$$5/1e6,$$9}'
