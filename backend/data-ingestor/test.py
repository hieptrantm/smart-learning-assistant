from ingestor.engine import ChunkingEngine

if __name__ == "__main__":
    engine = ChunkingEngine()
    result = engine.run_pipeline(
        file_path="ingestor/ktvm1.pdf",
        subject="Kinh tế Vi mô",
        language="Vietnamese"
    )
    print(result)