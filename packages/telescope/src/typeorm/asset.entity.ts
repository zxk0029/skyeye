import { Column, Entity, PrimaryColumn } from 'typeorm';

@Entity()
export class Asset {
  @PrimaryColumn({ type: 'bigint', name: 'hash' })
  id: number;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ type: 'int' })
  uint: number;

  @Column({ type: 'boolean' })
  is_stable: boolean;

  @Column({ type: 'varchar', length: 255 })
  status: string;
}
