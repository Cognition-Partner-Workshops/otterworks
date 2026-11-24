package com.otterworks.rating.controller;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.dto.QuoteForm;
import com.otterworks.rating.model.Quote;
import com.otterworks.rating.service.RatingService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseBody;

@Controller
public class QuoteController {

    private final RatingService rating;
    private final QuoteAuditStore audit;

    public QuoteController(RatingService rating, QuoteAuditStore audit) {
        this.rating = rating;
        this.audit = audit;
    }

    @GetMapping("/")
    public String page(Model model) {
        model.addAttribute("form", QuoteForm.example());
        return "quote";
    }

    @PostMapping("/")
    public String quote(@Valid @ModelAttribute("form") QuoteForm form, BindingResult errors, Model model) {
        if (!errors.hasErrors()) {
            Quote quote = rating.rate(form.toPolicy());
            model.addAttribute("quote", quote);
            model.addAttribute("reference", audit.save(quote));
        }
        return "quote";
    }

    @PostMapping("/api/quotes")
    @ResponseBody
    public ResponseEntity<Quote> api(@Valid @RequestBody QuoteForm form) {
        Quote quote = rating.rate(form.toPolicy());
        audit.save(quote);
        return ResponseEntity.ok(quote);
    }
}
