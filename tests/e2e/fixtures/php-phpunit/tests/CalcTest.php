<?php

use PHPUnit\Framework\TestCase;

require_once __DIR__ . '/../src/Calc.php';

final class CalcTest extends TestCase
{
    public function testAdultAt18(): void
    {
        $this->assertTrue(Calc::isAdult(18));
    }

    public function testAdultAt30(): void
    {
        $this->assertTrue(Calc::isAdult(30));
    }
}
