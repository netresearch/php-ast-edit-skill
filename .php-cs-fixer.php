<?php

declare (strict_types=1);
/*
 * The rules this repository is written to.
 *
 * php-ast-edit owns line breaking — no php-cs-fixer rule has a concept of line width, so
 * nothing here contradicts the printer. Everything below is the token-level half of the
 * fixed point: what the printer has no opinion about.
 */
$finder = PhpCsFixer\Finder::create()->in(__DIR__)->exclude(['vendor', 'dist', 'node_modules'])->notPath('tests/fixtures');
return (new PhpCsFixer\Config())->setRiskyAllowed(true)->setFinder($finder)->setRules(
    [
        '@PSR12' => true,
        'declare_strict_types' => true,
        // These four put back what canonical printing removes. `doctor` names them, because
        // without them a normalisation loses layout that a rule could have restored.
        'declare_parentheses' => true,
        'class_attributes_separation' => ['elements' => ['method' => 'one', 'property' => 'one', 'const' => 'one']],
        'blank_line_before_statement' => [
            'statements' => [
                'break',
                'continue',
                'declare',
                'return',
                'throw',
                'try',
                'if',
                'foreach',
                'for',
                'while',
                'switch',
                'do',
                'phpdoc',
            ],
        ],
        // The licence header sits directly after the tag here, so no blank line between them.
        'blank_line_after_opening_tag' => false,
        'single_line_empty_body' => true,
        'no_unused_imports' => true,
        'ordered_imports' => ['sort_algorithm' => 'alpha'],
        'trailing_comma_in_multiline' => ['elements' => ['arrays', 'arguments', 'parameters']],
        'array_syntax' => ['syntax' => 'short'],
        'no_superfluous_phpdoc_tags' => false,
    ]
);
