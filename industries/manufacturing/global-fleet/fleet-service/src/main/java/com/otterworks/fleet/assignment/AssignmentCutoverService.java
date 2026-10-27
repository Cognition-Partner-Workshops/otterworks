package com.otterworks.fleet.assignment;

import com.otterworks.fleet.domain.AssignmentRepository;
import com.otterworks.fleet.domain.DoubleHolderConfirmation;
import com.otterworks.fleet.domain.DoubleHolderConfirmationRepository;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AssignmentCutoverService {

    private static final int RECORD_LENGTH = 64;

    private final AssignmentRepository assignmentRepository;
    private final DoubleHolderConfirmationRepository confirmationRepository;
    private final String unloadPath;
    private final Clock clock;

    public AssignmentCutoverService(
            AssignmentRepository assignmentRepository,
            DoubleHolderConfirmationRepository confirmationRepository,
            @Value("${fleet.assignment.legacy-assignment-unload:}") String unloadPath,
            ObjectProvider<Clock> clockProvider) {
        this.assignmentRepository = assignmentRepository;
        this.confirmationRepository = confirmationRepository;
        this.unloadPath = unloadPath;
        this.clock = clockProvider.getIfAvailable(Clock::systemUTC);
    }

    @Transactional(readOnly = true)
    public List<DoubleHolderView> doubleHolders() {
        List<DoubleHolderView> holders = new ArrayList<>(unloadHolders());
        holders.addAll(serviceHolders());
        return holders.stream()
                .sorted(Comparator.comparing(DoubleHolderView::employeeNo)
                        .thenComparing(DoubleHolderView::employmentLegacyRef)
                        .thenComparing(DoubleHolderView::source))
                .toList();
    }

    @Transactional
    public ConfirmationView confirm(
            String employmentLegacyRef,
            ConfirmationRequest request) {
        if (request == null || request.assignmentLegacyRef() == null || request.returnDate() == null) {
            throw new AssignmentException("CONFIRMATION_FIELDS_REQUIRED");
        }
        DoubleHolderView holder = doubleHolders().stream()
                .filter(candidate -> candidate.employmentLegacyRef().equals(employmentLegacyRef))
                .findFirst()
                .orElseThrow(() -> new AssignmentException(
                        "DOUBLE_HOLDER_NOT_FOUND", "Unknown double holder", HttpStatus.NOT_FOUND));
        DoubleHolderAssignmentView assignment = holder.assignments().stream()
                .filter(candidate -> Objects.equals(candidate.legacyRef(), request.assignmentLegacyRef()))
                .findFirst()
                .orElseThrow(() -> new AssignmentException("ASSIGNMENT_NOT_OPEN_FOR_HOLDER"));
        if (request.returnDate().isBefore(assignment.startDate())) {
            throw new AssignmentException("RETURN_DATE_BEFORE_START");
        }
        DoubleHolderConfirmation confirmation = confirmationRepository.save(
                new DoubleHolderConfirmation(
                        employmentLegacyRef,
                        request.assignmentLegacyRef(),
                        request.returnDate(),
                        clock.instant()));
        return new ConfirmationView(
                employmentLegacyRef,
                confirmation.getAssignmentLegacyRef(),
                confirmation.getConfirmedReturnDate(),
                confirmation.getConfirmedAt());
    }

    private List<DoubleHolderView> unloadHolders() {
        if (unloadPath == null || unloadPath.isBlank()) {
            return List.of();
        }
        byte[] bytes;
        try {
            Path path = Path.of(unloadPath);
            if (!Files.exists(path)) {
                return List.of();
            }
            bytes = Files.readAllBytes(path);
        } catch (IOException exception) {
            throw new IllegalStateException("Cannot read legacy assignment unload", exception);
        }
        if (bytes.length % RECORD_LENGTH != 0) {
            throw new IllegalStateException("Legacy assignment unload must contain fixed 64-byte records");
        }

        Map<String, UnloadHolder> grouped = new LinkedHashMap<>();
        for (int offset = 0; offset < bytes.length; offset += RECORD_LENGTH) {
            String endDate = field(bytes, offset, 44, 8);
            if (!"00000000".equals(endDate)) {
                continue;
            }
            String employeeNo = field(bytes, offset, 10, 8);
            String dbKey = field(bytes, offset, 18, 10);
            String employmentRef = "MF:" + dbKey;
            String key = employeeNo + "\u0000" + employmentRef;
            UnloadHolder holder = grouped.computeIfAbsent(
                    key, ignored -> new UnloadHolder(employeeNo, employmentRef));
            holder.assignments.add(new DoubleHolderAssignmentView(
                    field(bytes, offset, 0, 10),
                    field(bytes, offset, 28, 8),
                    parseDate(field(bytes, offset, 36, 8)),
                    field(bytes, offset, 52, 2)));
        }

        return grouped.values().stream()
                .filter(holder -> holder.assignments.size() > 1)
                .filter(holder -> !confirmationRepository.existsById(holder.employmentLegacyRef))
                .map(holder -> new DoubleHolderView(
                        holder.employeeNo,
                        holder.employmentLegacyRef,
                        "LEGACY_UNLOAD",
                        List.copyOf(holder.assignments)))
                .toList();
    }

    private List<DoubleHolderView> serviceHolders() {
        Map<Long, List<Object[]>> byPerson = new LinkedHashMap<>();
        for (Object[] row : assignmentRepository.findAllOpenAssignmentRows()) {
            byPerson.computeIfAbsent((Long) row[0], ignored -> new ArrayList<>()).add(row);
        }
        List<DoubleHolderView> holders = new ArrayList<>();
        for (List<Object[]> rows : byPerson.values()) {
            if (rows.size() < 2) {
                continue;
            }
            Object[] first = rows.get(0);
            String employmentRef = (String) first[2];
            if (employmentRef == null || employmentRef.isBlank()) {
                employmentRef = "DB:" + first[0];
            }
            if (confirmationRepository.existsById(employmentRef)) {
                continue;
            }
            List<DoubleHolderAssignmentView> assignments = rows.stream()
                    .map(row -> new DoubleHolderAssignmentView(
                            (String) row[4],
                            String.valueOf(row[5]),
                            (LocalDate) row[7],
                            (String) row[8]))
                    .toList();
            holders.add(new DoubleHolderView(
                    (String) first[1],
                    employmentRef,
                    "SERVICE",
                    assignments));
        }
        return holders;
    }

    private static String field(byte[] bytes, int recordOffset, int fieldOffset, int length) {
        return new String(
                bytes,
                recordOffset + fieldOffset,
                length,
                StandardCharsets.US_ASCII).trim();
    }

    private static LocalDate parseDate(String value) {
        try {
            return LocalDate.parse(value, DateTimeFormatter.BASIC_ISO_DATE);
        } catch (DateTimeParseException exception) {
            throw new IllegalStateException("Invalid start date in legacy assignment unload", exception);
        }
    }

    private static final class UnloadHolder {

        private final String employeeNo;
        private final String employmentLegacyRef;
        private final List<DoubleHolderAssignmentView> assignments = new ArrayList<>();

        private UnloadHolder(String employeeNo, String employmentLegacyRef) {
            this.employeeNo = employeeNo;
            this.employmentLegacyRef = employmentLegacyRef;
        }
    }
}
