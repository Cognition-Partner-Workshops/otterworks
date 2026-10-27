package com.otterworks.fleet.assignment;

import java.sql.SQLException;
import java.util.List;
import java.util.UUID;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class AssignmentController {

    private final AssignmentService assignmentService;
    private final AssignmentCutoverService cutoverService;

    public AssignmentController(
            AssignmentService assignmentService,
            AssignmentCutoverService cutoverService) {
        this.assignmentService = assignmentService;
        this.cutoverService = cutoverService;
    }

    @GetMapping("/assignments/pool")
    public List<PoolVehicle> pool() {
        return assignmentService.pool();
    }

    @GetMapping("/assignments/vehicle-rules")
    public VehicleRulesResponse vehicleRules() {
        return assignmentService.vehicleRules();
    }

    @GetMapping("/car-requests/drafts/{employeeNo}")
    public DraftView getDraft(@PathVariable("employeeNo") String employeeNo) {
        return assignmentService.getDraft(employeeNo);
    }

    @PutMapping("/car-requests/drafts/{employeeNo}")
    public DraftView putDraft(
            @PathVariable("employeeNo") String employeeNo,
            @RequestBody DraftUpdateRequest request) {
        return assignmentService.putDraft(employeeNo, request);
    }

    @DeleteMapping("/car-requests/drafts/{employeeNo}")
    public ResponseEntity<Void> discardDraft(@PathVariable("employeeNo") String employeeNo) {
        assignmentService.discardDraft(employeeNo);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/car-requests/drafts/{employeeNo}/submit")
    public ResponseEntity<?> submit(
            @PathVariable("employeeNo") String employeeNo,
            @RequestBody(required = false) SubmitRequest request) {
        if (request == null || request.draftId() == null) {
            throw new AssignmentException("DRAFT_ID_REQUIRED");
        }
        try {
            SubmitOutcome outcome = assignmentService.submit(employeeNo, request.draftId());
            return ResponseEntity.status(outcome.replay() ? HttpStatus.OK : HttpStatus.CREATED)
                    .body(outcome.result());
        } catch (StalePoolVehicleException exception) {
            return staleResponse(employeeNo, request.draftId());
        } catch (DataIntegrityViolationException exception) {
            if (!isOpenVehicleConstraint(exception)) {
                throw exception;
            }
            return staleResponse(employeeNo, request.draftId());
        }
    }

    @GetMapping("/employees/{employeeNo}/car")
    public EmployeeCarView currentCar(@PathVariable("employeeNo") String employeeNo) {
        return assignmentService.currentCar(employeeNo);
    }

    @GetMapping("/assignments/cutover/double-holders")
    public List<DoubleHolderView> doubleHolders() {
        return cutoverService.doubleHolders();
    }

    @PostMapping("/assignments/cutover/double-holders/{employmentLegacyRef}/confirmations")
    public ResponseEntity<ConfirmationView> confirmDoubleHolder(
            @PathVariable("employmentLegacyRef") String employmentLegacyRef,
            @RequestBody ConfirmationRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(cutoverService.confirm(employmentLegacyRef, request));
    }

    private ResponseEntity<CarNoLongerAvailableResponse> staleResponse(String employeeNo, UUID draftId) {
        assignmentService.returnDraftToVehicleChoice(employeeNo, draftId);
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new CarNoLongerAvailableResponse(
                        "CAR_NO_LONGER_AVAILABLE",
                        "The selected car is no longer available",
                        assignmentService.pool()));
    }

    private static boolean isOpenVehicleConstraint(Throwable exception) {
        Throwable current = exception;
        while (current != null) {
            if (current.getMessage() != null
                    && current.getMessage().contains("assignment_one_open_per_vehicle")) {
                return true;
            }
            if (current instanceof SQLException sqlException) {
                for (SQLException next = sqlException.getNextException(); next != null; next = next.getNextException()) {
                    if (next.getMessage() != null
                            && next.getMessage().contains("assignment_one_open_per_vehicle")) {
                        return true;
                    }
                }
            }
            current = current.getCause();
        }
        return false;
    }
}
