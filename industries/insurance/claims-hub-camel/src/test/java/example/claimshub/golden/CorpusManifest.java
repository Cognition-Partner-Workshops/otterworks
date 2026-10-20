package example.claimshub.golden;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import org.yaml.snakeyaml.Yaml;

/**
 * Reads {@code corpus/manifest.yaml} of the BizTalk fixture, the same manifest {@code tools/xslt-golden}
 * runs, so the Java side measures every map over exactly the inputs and goldens Saxon used.
 */
public final class CorpusManifest {

    public static final String FIXTURE_PROPERTY = "claims.fixture.dir";

    public record MapSpec(String name, String xslt, Path inputs, Path golden, String suffix) {

        public List<Path> inputFiles() {
            try (Stream<Path> files = Files.list(inputs)) {
                return files.filter(p -> p.getFileName().toString().endsWith(".xml")).sorted().toList();
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }

        public Path goldenFor(Path input) {
            String file = input.getFileName().toString();
            return golden.resolve(file.substring(0, file.lastIndexOf('.')) + suffix);
        }
    }

    private final Path fixtureDir;
    private final List<MapSpec> maps;

    private CorpusManifest(Path fixtureDir, List<MapSpec> maps) {
        this.fixtureDir = fixtureDir;
        this.maps = maps;
    }

    public static Path fixtureDir() {
        String configured = System.getProperty(FIXTURE_PROPERTY, "../biztalk-claims-intake");
        return Path.of(configured).toAbsolutePath().normalize();
    }

    public static CorpusManifest load() {
        return load(fixtureDir());
    }

    @SuppressWarnings("unchecked")
    public static CorpusManifest load(Path fixtureDir) {
        Path manifest = fixtureDir.resolve("corpus/manifest.yaml");
        Map<String, Object> doc;
        try (InputStream in = Files.newInputStream(manifest)) {
            doc = new Yaml().load(in);
        } catch (IOException e) {
            throw new UncheckedIOException("cannot read " + manifest, e);
        }
        Path base = manifest.getParent().resolve(String.valueOf(doc.getOrDefault("base", "."))).normalize();
        List<MapSpec> maps = ((List<Map<String, Object>>) doc.get("maps")).stream()
                .map(m -> new MapSpec(
                        (String) m.get("name"),
                        (String) m.get("xslt"),
                        base.resolve((String) m.get("inputs")).normalize(),
                        base.resolve((String) m.get("golden")).normalize(),
                        (String) m.getOrDefault("suffix", ".xml")))
                .toList();
        return new CorpusManifest(fixtureDir, maps);
    }

    public Path fixture() {
        return fixtureDir;
    }

    public List<MapSpec> maps() {
        return maps;
    }

    public MapSpec map(String name) {
        return maps.stream().filter(m -> m.name().equals(name)).findFirst()
                .orElseThrow(() -> new IllegalArgumentException("map not in corpus/manifest.yaml: " + name));
    }
}
