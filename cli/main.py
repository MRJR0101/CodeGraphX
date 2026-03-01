"""
CodeGraphX 2.0 - Unified CLI
Commands:
  codegraphx ingest <repo>
  codegraphx analyze
  codegraphx metrics
  codegraphx semantic-query "<question>"
  codegraphx cypher "<query>"
  codegraphx reset
"""
import sys
import json
import click
from pathlib import Path

from codegraphx.core.config import config
from codegraphx.core.pipeline import IngestionPipeline
from codegraphx.llm.query_interface import NLToCypherTranslator, QueryValidator, SubgraphSummarizer


# Global pipeline instance (persists across commands in interactive mode)
_pipeline: IngestionPipeline = None


def _get_pipeline(neo4j: bool = False) -> IngestionPipeline:
    """Get or create the pipeline instance."""
    global _pipeline
    if _pipeline is None:
        connection = None
        if neo4j:
            from codegraphx.schema.neo4j_schema import Neo4jConnection
            connection = Neo4jConnection(
                uri=config.neo4j.uri,
                user=config.neo4j.user,
                password=config.neo4j.password,
            )
            connection.connect()
            connection.initialize_schema()
        _pipeline = IngestionPipeline(neo4j_connection=connection)
    return _pipeline


@click.group()
@click.version_option(version="0.2.0", prog_name="CodeGraphX")
def cli():
    """CodeGraphX 2.0 - Unified Code Intelligence Platform"""
    pass


@cli.command()
@click.argument("repo", type=click.Path(exists=True))
@click.option("--language", "-l", default="python",
              type=click.Choice(["python", "javascript"]),
              help="Primary language of the repository.")
@click.option("--neo4j", is_flag=True, default=False,
              help="Write results to Neo4j database.")
@click.option("--skip-semantic", is_flag=True, default=False,
              help="Skip semantic enrichment (Phase 5).")
def ingest(repo, language, neo4j, skip_semantic):
    """Ingest a repository through all analysis phases.

    REPO is the path to the repository root directory.
    """
    click.echo(f"╔═══════════════════════════════════════════╗")
    click.echo(f"║  CodeGraphX 2.0 - Repository Ingestion    ║")
    click.echo(f"╚═══════════════════════════════════════════╝")
    click.echo(f"  Repository: {repo}")
    click.echo(f"  Language:   {language}")
    click.echo(f"  Neo4j:      {'enabled' if neo4j else 'disabled'}")
    click.echo(f"  Semantic:   {'enabled' if not skip_semantic else 'disabled'}")
    click.echo()

    pipeline = _get_pipeline(neo4j=neo4j)
    ctx = pipeline.ingest(
        repo_path=repo,
        language=language,
        write_to_neo4j=neo4j,
        skip_semantic=skip_semantic,
    )

    click.echo(f"\n  Files parsed:    {len(ctx.ast_nodes)}")
    click.echo(f"  Arch nodes:      {len(ctx.arch_nodes)}")
    click.echo(f"  Arch rels:       {len(ctx.arch_relationships)}")
    click.echo(f"  CPG nodes:       {len(ctx.cpg_nodes)}")
    click.echo(f"  CPG rels:        {len(ctx.cpg_relationships)}")
    click.echo(f"  Errors:          {len(ctx.errors)}")


@cli.command()
def analyze():
    """Display architectural analysis results."""
    pipeline = _get_pipeline()
    if not pipeline.context:
        click.echo("Error: No repository ingested. Run 'ingest' first.", err=True)
        sys.exit(1)

    ctx = pipeline.context
    click.echo(f"\n═══ Architectural Analysis ═══")
    click.echo(f"Total nodes:         {len(ctx.arch_nodes)}")
    click.echo(f"Total relationships: {len(ctx.arch_relationships)}")

    # Node type breakdown
    from collections import Counter
    label_counts = Counter(n.label.value if hasattr(n.label, 'value') else str(n.label)
                           for n in ctx.arch_nodes)
    click.echo(f"\nNode Types:")
    for label, count in sorted(label_counts.items()):
        click.echo(f"  {label}: {count}")

    # Relationship type breakdown
    rel_counts = Counter(r.type.value if hasattr(r.type, 'value') else str(r.type)
                         for r in ctx.arch_relationships)
    click.echo(f"\nRelationship Types:")
    for rtype, count in sorted(rel_counts.items()):
        click.echo(f"  {rtype}: {count}")

    # Top connected nodes
    from codegraphx.extractors.architecture_extractor import ArchitectureExtractor, ArchitectureValidator
    extractor = ArchitectureExtractor()
    extractor.nodes = {n.id: n for n in ctx.arch_nodes}
    extractor.relationships = ctx.arch_relationships
    validator = ArchitectureValidator(extractor)

    hotspots = validator.find_dependency_hotspots(10)
    if hotspots:
        click.echo(f"\nDependency Hotspots:")
        for name, count in hotspots:
            click.echo(f"  {name}: {count} connections")

    dead = validator.find_dead_modules()
    if dead:
        click.echo(f"\nDead Modules ({len(dead)}):")
        for m in dead[:10]:
            click.echo(f"  {m.name} ({m.file_path})")


@cli.command()
def metrics():
    """Display computed metrics and risk analysis."""
    pipeline = _get_pipeline()
    if not pipeline.metrics_results:
        click.echo("Error: No metrics computed. Run 'ingest' first.", err=True)
        sys.exit(1)

    summary = pipeline.get_metrics_summary()

    click.echo(f"\n═══ Metrics Summary ═══")
    click.echo(f"Nodes analyzed:    {summary['total_nodes_analyzed']}")
    click.echo(f"Avg complexity:    {summary['avg_complexity']:.1f}")
    click.echo(f"Max complexity:    {summary['max_complexity']}")
    click.echo(f"Risk-flagged:      {summary['risk_flagged_nodes']}")

    if summary['risk_details']:
        click.echo(f"\nRisk Details:")
        for detail in summary['risk_details']:
            for flag in detail['flags']:
                click.echo(f"  ⚠ {flag}")


@cli.command("semantic-query")
@click.argument("question")
@click.option("--top-k", "-k", default=None, type=int, help="Number of results.")
def semantic_query(question, top_k):
    """Run a semantic query against the enriched graph.

    QUESTION is a natural language question about the codebase.
    """
    pipeline = _get_pipeline()
    try:
        kwargs = {}
        if top_k:
            kwargs["top_k"] = top_k
        results = pipeline.semantic_query(question, **kwargs)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"\n═══ Semantic Query Results ═══")
    click.echo(f"Query: {question}")
    click.echo(f"Results: {len(results)}\n")

    for i, r in enumerate(results, 1):
        seed_marker = "★" if r.get("is_seed") else " "
        sim = r.get("similarity", 0.0)
        click.echo(f"  {seed_marker} [{i}] {r['name']} ({r['label']})")
        click.echo(f"       File: {r['file_path']}")
        click.echo(f"       Similarity: {sim:.4f}")
        if r.get("docstring"):
            click.echo(f"       Doc: {r['docstring'][:100]}...")
        click.echo()


@cli.command("cypher")
@click.argument("query")
def cypher(query):
    """Execute a validated Cypher query (read-only).

    QUERY is a Cypher query string.
    """
    validator = QueryValidator()
    result = validator.validate(query)

    if not result["valid"]:
        click.echo(f"Query validation failed:", err=True)
        for error in result["errors"]:
            click.echo(f"  ✗ {error}", err=True)
        sys.exit(1)

    click.echo(f"Validated query: {result['cleaned']}")
    click.echo("(Execute against Neo4j connection for results)")


@cli.command()
@click.confirmation_option(prompt="This will wipe all data. Are you sure?")
def reset():
    """Reset the database (wipe all nodes and relationships)."""
    pipeline = _get_pipeline(neo4j=True)
    if pipeline.connection:
        pipeline.connection.reset_database()
        click.echo("Database reset complete.")
    else:
        click.echo("No Neo4j connection available.", err=True)


@cli.command("serve-api")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--reload", is_flag=True, default=False, help="Enable autoreload.")
def serve_api(host, port, reload):
    """Run the platform API server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn not installed. Install with 'pip install uvicorn'.", err=True)
        sys.exit(1)

    click.echo(f"Starting API on http://{host}:{port}")
    uvicorn.run("codegraphx.cg_platform.api.app:create_app", host=host, port=port, reload=reload, factory=True)


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
