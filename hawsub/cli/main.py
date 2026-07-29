"""
Hawsub CLI & GUI Application Entry Point.
"""

import click
import sys
import os
import json
from hawsub import __version__
from hawsub.config.loader import load_config
from hawsub.core.orchestration.pipeline import DurablePipeline
from hawsub.core.normalization.sorani import SoraniNormalizer
from hawsub.benchmark.suite import BenchmarkSuite
from hawsub.providers.factory import get_provider


@click.group()
@click.version_option(version=__version__, message="Hawsub version %(version)s")
def cli():
    """Hawsub — Professional English -> Central Kurdish (Sorani, ckb) Subtitle Localization System."""
    pass


@cli.command()
@click.option("--input", "-i", "input_path", required=True, type=click.Path(exists=True), help="Path to input English SRT/VTT subtitle file.")
@click.option("--project-id", "-p", default="movie_project", help="Unique project identifier.")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), help="Path to custom hawsub.yaml configuration file.")
@click.option("--output-dir", "-o", default="output", help="Output directory for generated subtitle files.")
def process(input_path: str, project_id: str, config_path: str, output_dir: str):
    """Process an English subtitle file through full context-aware Sorani localization pipeline."""
    try:
        click.echo(f"Initializing Hawsub pipeline for project: {project_id}")
        cfg = load_config(config_path)
        
        pipeline = DurablePipeline(project_id=project_id, config=cfg)
        results = pipeline.process_file(input_path, output_dir=output_dir)

        click.echo(click.style("✓ Localization complete!", fg="green", bold=True))
        click.echo(f"  SRT Export: {results['srt']}")
        click.echo(f"  ASS Export: {results['ass']}")
        click.echo(f"  VTT Export: {results['vtt']}")
        click.echo(f"  Debug HTML: {results['bilingual_html']}")
        click.echo(f"  QC Report : {results['qc_report']}")

        if "quality_summary" in results:
            qs = results["quality_summary"]
            click.echo(f"\n  Quality: {qs['pass_rate']}% pass rate, {qs['critical_issues']} critical issues")
    except FileNotFoundError as e:
        click.echo(click.style(f"✗ File not found: {e}", fg="red"), err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(click.style(f"✗ Invalid input: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"✗ Pipeline error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--dataset", "-d", default="tests/gold/gold_dataset.json", type=click.Path(exists=True), help="Gold benchmark dataset path.")
@click.option("--provider", default="mock", help="Provider to evaluate (google | openai | mock).")
@click.option("--model", default="gemini-2.5-pro", help="Model name to evaluate.")
def benchmark(dataset: str, provider: str, model: str):
    """Run cinematic benchmark evaluation on gold dataset pairs."""
    try:
        click.echo(f"Running Hawsub benchmark suite on {dataset} using provider={provider}, model={model}...")
        
        p_model = get_provider(provider_name=provider, model_name=model)
        suite = BenchmarkSuite(dataset_path=dataset)
        report = suite.evaluate_model(p_model)

        click.echo("\n" + "=" * 50)
        click.echo(click.style(f"Hawsub Benchmark Results [{report.provider_name} / {report.model_name}]", bold=True))
        click.echo("=" * 50)
        click.echo(f"Total Test Items    : {report.total_items}")
        click.echo(f"Passed Items        : {report.passed_items}")
        click.echo(f"Literal Error Count : {report.literal_error_count}")
        click.echo(click.style(f"Overall Score       : {report.overall_benchmark_score * 100:.1f}%", fg="cyan", bold=True))
        click.echo("=" * 50)
    except Exception as e:
        click.echo(click.style(f"✗ Benchmark error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--text", "-t", required=True, help="Input Kurdish text to normalize.")
def normalize(text: str):
    """Normalize Sorani Kurdish text to canonical orthography."""
    norm = SoraniNormalizer()
    res = norm.normalize(text)
    click.echo(f"Input     : {text}")
    click.echo(f"Normalized: {res}")


@cli.command()
@click.option("--port", default=8080, help="Port to run Hawsub GUI Workstation application server.")
def gui(port: int):
    """Launch interactive Hawsub Subtitle Localization GUI Application."""
    from hawsub.ui.server import start_gui
    start_gui(port=port)


@cli.command()
@click.option("--input", "-i", "input_path", required=True, type=click.Path(exists=True), help="Path to input subtitle file.")
def inspect(input_path: str):
    """Inspect and analyze subtitle file statistics (cue count, duration, words, CPS)."""
    from hawsub.core.ingest.parser import SubtitleParser, format_timestamp_srt

    try:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        cues = SubtitleParser.parse_auto(content, input_path)
        if not cues:
            click.echo(click.style("Error: No subtitle cues parsed.", fg="red"))
            return

        total_cues = len(cues)
        total_duration_sec = (cues[-1].end_ms - cues[0].start_ms) / 1000.0 if total_cues > 0 else 0
        total_words = sum(len(c.clean_source_text.split()) for c in cues)
        avg_cps = sum(len(c.clean_source_text) / max(0.1, c.duration_ms / 1000.0) for c in cues) / total_cues if total_cues > 0 else 0

        click.echo("\n" + "=" * 50)
        click.echo(click.style(f"Hawsub Subtitle Inspector — {os.path.basename(input_path)}", bold=True))
        click.echo("=" * 50)
        click.echo(f"Total Cues        : {total_cues}")
        click.echo(f"Total Duration    : {total_duration_sec / 60.0:.2f} minutes ({format_timestamp_srt(cues[0].start_ms)} -> {format_timestamp_srt(cues[-1].end_ms)})")
        click.echo(f"Total Word Count  : {total_words} words")
        click.echo(f"Average Source CPS: {avg_cps:.1f} cps")
        click.echo("=" * 50)
    except Exception as e:
        click.echo(click.style(f"✗ Inspect error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--input", "-i", "input_path", required=True, type=click.Path(exists=True), help="Path to input subtitle file.")
@click.option("--provider", default="mock", help="Provider for cost estimation.")
@click.option("--model", default="gemini-2.5-flash", help="Model name for cost estimation.")
@click.option("--budget", default=10.0, type=float, help="Maximum budget in USD.")
def estimate(input_path: str, provider: str, model: str, budget: float):
    """Estimate translation cost before running the pipeline."""
    from hawsub.core.ingest.parser import SubtitleParser
    from hawsub.core.cost.budget import TokenBudget

    try:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        cues = SubtitleParser.parse_auto(content, input_path)
        if not cues:
            click.echo(click.style("Error: No subtitle cues parsed.", fg="red"))
            return

        avg_len = sum(len(c.clean_source_text) for c in cues) // max(1, len(cues))
        tb = TokenBudget(max_cost_usd=budget, model_name=model)
        est = tb.estimate_full_file(total_cues=len(cues), avg_source_length=avg_len)

        click.echo("\n" + "=" * 50)
        click.echo(click.style("Hawsub Cost Estimate", bold=True))
        click.echo("=" * 50)
        click.echo(f"File          : {os.path.basename(input_path)}")
        click.echo(f"Total Cues    : {est.total_cues}")
        click.echo(f"Model         : {model}")
        click.echo(f"Est. Input    : ~{est.estimated_input_tokens:,} tokens")
        click.echo(f"Est. Output   : ~{est.estimated_output_tokens:,} tokens")
        click.echo(click.style(f"Est. Cost     : ${est.estimated_cost_usd:.4f} USD", fg="cyan", bold=True))
        click.echo(f"Budget        : ${budget:.2f} USD")

        if est.estimated_cost_usd > budget:
            click.echo(click.style("⚠ Estimated cost exceeds budget!", fg="yellow"))
        else:
            click.echo(click.style("✓ Within budget.", fg="green"))
        click.echo("=" * 50)
    except Exception as e:
        click.echo(click.style(f"✗ Estimate error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--input", "-i", "input_path", required=True, type=click.Path(exists=True), help="Path to Sorani subtitle file to validate.")
def validate(input_path: str):
    """Validate a Sorani Kurdish subtitle file for quality issues."""
    from hawsub.core.ingest.parser import SubtitleParser

    try:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        cues = SubtitleParser.parse_auto(content, input_path)
        if not cues:
            click.echo(click.style("Error: No subtitle cues parsed.", fg="red"))
            return

        normalizer = SoraniNormalizer()
        total_issues = 0
        issue_counts = {"kurmanji": 0, "untranslated": 0, "ezafe": 0, "llm_errors": 0}

        for cue in cues:
            text = cue.target_text or cue.source_text
            result = normalizer.validate_sorani_text(text)
            for category, issues in result.items():
                if issues:
                    total_issues += len(issues)
                    issue_counts[category] += len(issues)
                    for issue in issues:
                        click.echo(f"  Cue {cue.id} [{category}]: {issue}")

        click.echo("\n" + "=" * 50)
        click.echo(click.style(f"Validation Summary — {os.path.basename(input_path)}", bold=True))
        click.echo("=" * 50)
        click.echo(f"Total Cues     : {len(cues)}")
        click.echo(f"Total Issues   : {total_issues}")
        for cat, count in issue_counts.items():
            if count:
                click.echo(f"  {cat}: {count}")

        if total_issues == 0:
            click.echo(click.style("✓ No issues found!", fg="green"))
        else:
            click.echo(click.style(f"⚠ {total_issues} issues found.", fg="yellow"))
        click.echo("=" * 50)
    except Exception as e:
        click.echo(click.style(f"✗ Validation error: {e}", fg="red"), err=True)
        sys.exit(1)


@cli.command()
@click.option("--export", "-e", "export_path", type=click.Path(), help="Export corrections as JSONL training data.")
@click.option("--db", default="hawsub_feedback.db", help="Feedback database path.")
@click.option("--project", "-p", default=None, help="Filter by project ID.")
@click.option("--glossary-candidates", is_flag=True, help="Show frequently corrected phrases (glossary candidates).")
def feedback(export_path: str, db: str, project: str, glossary_candidates: bool):
    """Manage human correction feedback data."""
    from hawsub.core.review.feedback import FeedbackStore

    try:
        store = FeedbackStore(db_path=db)

        if glossary_candidates:
            candidates = store.get_frequent_corrections(min_count=2)
            if candidates:
                click.echo(click.style("\nGlossary Candidates (frequently corrected):", bold=True))
                for c in candidates:
                    click.echo(f"  '{c['source_text']}' → '{c['corrected_translation']}' ({c['frequency']}x)")
            else:
                click.echo("No frequent correction patterns found yet.")
            return

        if export_path:
            count = store.export_training_data(export_path, project_id=project)
            click.echo(click.style(f"✓ Exported {count} training records to {export_path}", fg="green"))
            return

        # Default: show recent corrections
        corrections = store.get_corrections(project_id=project, limit=20)
        if corrections:
            click.echo(click.style(f"\nRecent Corrections ({len(corrections)}):", bold=True))
            for c in corrections:
                click.echo(f"  [{c.correction_type}] '{c.source_text[:40]}' → '{c.corrected_translation[:40]}'")
        else:
            click.echo("No corrections recorded yet.")
    except Exception as e:
        click.echo(click.style(f"✗ Feedback error: {e}", fg="red"), err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()

