<?php
declare(strict_types=1);

final class CustomerService
{
    public function load(int $id): string
    {
        $sql = 'SELECT * FROM customer WHERE id = ?';
        $customer = $this->repository->oldFind($id);
        return $customer->name;
    }
}
